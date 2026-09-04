import base64
import logging
import traceback
from datetime import datetime, timedelta

from odoo import http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request
import xml.etree.ElementTree as ET

try:
    import xmlschema
    from xmlschema import XMLSchemaValidationError
    from xmlschema.exceptions import XMLSchemaTypeError
except ImportError:
    raise ImportError(
        'This module needs xmlschema to validate saf-t files. (pip3 install xmlschema)')

_logger = logging.getLogger(__name__)

VERSION = "1.04"
UNKNOWN = "Desconhecido"
XMLNS = r"urn:OECD:StandardAuditFile-Tax:PT_1.04_01"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = r"urn:OECD:StandardAuditFile-Tax:PT_1.04_01 .\SAFTPT1.04_01.xsd"
ISO8601 = "%Y-%m-%dT%H:%M:%S"
MAX_RECORDS = 25000

REQUIRED_FIELDS = [
    'date_start',
    'date_end',
]


class ArxiQualityApiClient(AuthSignupHome):
    """
    This class is responsible for handling the API requests; core functionalities:
    - Validate the request
    - Export the SAFT file
    - Manage conditional exports based on amount of records in a given date range
    """
    _webhook_url = '/export/saft'

    @http.route(_webhook_url, type='json', auth='none', methods=['POST'], csrf=False)
    def get_saft_xml_response(self, **post):
        """
        Receives a POST request with the following structure:
        curl -X POST https://girt-server-staging-14453231.dev.odoo.com/export/saft \
        -H "Content-Type: application/json" \
        -d '{
            "params": {
                "api_token": "YsyTef3U62evPE775ZlBWHmrZvTSorC",
                "saft_data": {
                    "date_start": "2024-09-01",
                    "date_end": "2024-09-30"
                    }
                }
        }'
        :param post: json request
        :return: json response
        """
        arr = []
        res = self.validate_request(post)
        if res != "OK":
            return res

        saft_data = post.get('saft_data')
        date_start = datetime.strptime(saft_data.get('date_start'), "%Y-%m-%d").date()
        date_end = datetime.strptime(saft_data.get('date_end'), "%Y-%m-%d").date()

        pt_domain = [('account_fiscal_country_id.code', '=', 'PT')]
        pt_company_ids = request.env['res.company'].sudo().search(pt_domain, order='id asc')

        domain = [('account_fiscal_country_id.code', '=', 'PT'),
                  ('company_registry', '!=', False),
                  ('commercial_registry', '!=', False),
                  ('l10n_pt_at_webservice', '=', True),
                  ("parent_id", "=", False),

                  ]
        cert_company_ids = request.env['res.company'].sudo().search(domain, order='id asc')
        if not cert_company_ids:
            return [{
                'status'             : 500,
                'response'           : "No company_ids matched the search.",
                'error:'             : "company_ids = [request.env['res.company'].sudo().search([('account_fiscal_country_id.code', '=', 'PT'), ('company_registry', '!=', False), ('commercial_registry', '!=', False), ('l10n_pt_at_webservice', '=', True)], order='id asc')]",
                'company_id'         : 0,
                'company_name'       : "None",
                'record_amount_total': 0,
                'record_amount'      : 0,
            }]

        pt_company_ids = pt_company_ids - cert_company_ids
        # TODO: Maybe warn the user that there are PT companies that were not flagged as certified
        for company_id in cert_company_ids:
            company_dict = self.export_saft(date_end, date_start, company_id)
            arr.append(company_dict)

        return arr

    def query_validate_saft_stock_move_keys(self, xml, date_start, date_end, wiz_get_company_ids):
        is_installed = request.env['ir.module.module'].sudo().search(
            [
                ('name', '=', 'l10n_pt_stock'),
                ('state', '=', 'installed')
            ])

        if is_installed:
            res = request.env['pt.transport'].sudo().search(
                [
                    ('validated_date', '>=', date_start),
                    ('inalterable_hash', '!=', False),
                    ('company_id', 'in', wiz_get_company_ids),
                    ('validated_date', '<=', date_end)], order='name')

            total_quant = 0
            total_lines = 0

            for doc in res:
                lines = []
                for line in doc.transport_line_ids:
                    total_quant += line.product_uom_qty if doc.status_id.code != 'A' else 0
                    lines.append(line)
                total_lines += len(lines)

            root = ET.fromstring(xml)

            quant_issued_text = False
            lines_issued_text = False
            namespace = {'ns': 'urn:OECD:StandardAuditFile-Tax:PT_1.04_01'}

            total_quantity_issued = root.find('ns:SourceDocuments/ns:MovementOfGoods/ns:TotalQuantityIssued', namespace)
            if total_quantity_issued is not None:
                quant_issued_text = total_quantity_issued.text

            number_of_movement_lines = root.find(
                'ns:SourceDocuments/ns:MovementOfGoods/ns:NumberOfMovementLines', namespace)
            if number_of_movement_lines is not None:
                lines_issued_text = number_of_movement_lines.text

            if lines_issued_text and quant_issued_text:
                issued_quant = float(quant_issued_text)
                if abs(issued_quant - total_quant) <= 0.02 and str(total_lines) == lines_issued_text:
                    _logger.info("Values match: TotalQuantityIssued and NumberOfMovementLines are correct.")
                    return False
                else:
                    return [{
                        'message'     : 'TotalQuantityIssued and NumberOfMovementLines are incorrect.',
                        'total_quant' : str(total_quant),
                        'issued_quant': quant_issued_text,
                        'total_lines' : str(total_lines),
                        'issued_lines': lines_issued_text
                    }]

        else:
            return False

    def query_validate_saft_payment_keys(self, xml):
        """
        Validates SAFT payment keys from the provided XML.
        Ensures that: PaymentAmount = GrossTotal + SettlementAmount (if present)
        Also validates credit amounts against total credit.
        Skips validation if CurrencyCode is not EUR.
        Returns a list of discrepancies found.
        """
        root = ET.fromstring(xml)
        namespace = {'ns': 'urn:OECD:StandardAuditFile-Tax:PT_1.04_01'}
        arr = []
        total_credit = root.find(".//ns:Payments/ns:TotalCredit", namespace)
        total_credit_amount = 0.0

        for payment in root.findall(".//ns:Payment", namespace):
            currency_code = payment.find("ns:DocumentTotals/ns:Currency/ns:CurrencyCode", namespace)
            if currency_code is not None and currency_code.text and currency_code.text != "EUR":
                continue  # skip validation for non-EUR payments

            payment_ref_no = payment.find("ns:PaymentRefNo", namespace)
            payment_amount = payment.find("ns:PaymentMethod/ns:PaymentAmount", namespace)
            gross_total = payment.find("ns:DocumentTotals/ns:GrossTotal", namespace)
            settlement_amount = payment.find("ns:DocumentTotals/ns:Settlement/ns:SettlementAmount", namespace)
            payment_status = payment.find("ns:DocumentStatus/ns:PaymentStatus", namespace)

            # Validate payment total
            if (
                    payment_ref_no is not None and
                    payment_amount is not None and
                    gross_total is not None
            ):
                gross_val = float(gross_total.text)
                settle_val = float(settlement_amount.text) if settlement_amount is not None else 0.0
                expected_payment = gross_val + settle_val
                actual_payment = float(payment_amount.text)

                if abs(expected_payment - actual_payment) > 0.02:
                    arr.append({
                        "PaymentRefNo"       : payment_ref_no.text,
                        "ExpectedAmount"     : f"{expected_payment:.2f}",
                        "ActualPaymentAmount": payment_amount.text,
                        "GrossTotal"         : gross_total.text,
                        "SettlementAmount"   : settlement_amount.text if settlement_amount is not None else "0.00"
                    })

            # Sum credit lines for validation
            for line in payment.findall(".//ns:Line", namespace):
                credit_amount = line.find("ns:CreditAmount", namespace)
                if credit_amount is not None and payment_status.text != "A":
                    total_credit_amount += float(credit_amount.text)

        if total_credit is not None:
            if abs(float(total_credit.text) - total_credit_amount) > 0.02:
                total_credit_error_arr = {
                    "TotalPaymentsCredit": total_credit.text,
                    "SummedCredit"       : round(total_credit_amount, 2)
                }
                arr.append(total_credit_error_arr)

        return arr

    def query_validate_saft_credit_totals(self, xml):
        root = ET.fromstring(xml)
        namespace = {'ns': 'urn:OECD:StandardAuditFile-Tax:PT_1.04_01'}
        errors = []

        # validate SalesInvoices
        total_sales_credit = root.find(".//ns:SalesInvoices/ns:TotalCredit", namespace)
        total_sales_credit_value = float(total_sales_credit.text) if total_sales_credit is not None else 0.0

        total_sales_credit_amount = 0.0
        for invoice in root.findall(".//ns:SalesInvoices/ns:Invoice", namespace):
            invoice_type = invoice.find("ns:InvoiceType", namespace)
            invoice_status = invoice.find("ns:DocumentStatus/ns:InvoiceStatus", namespace)

            if invoice_type is None or invoice_status is None:
                continue

            if invoice_type.text in ["FT", "NC", "FR", "FS"] and invoice_status.text != "A":
                for line in invoice.findall(".//ns:Line", namespace):
                    credit_amount = line.find("ns:CreditAmount", namespace)
                    if credit_amount is not None and credit_amount.text:
                        total_sales_credit_amount += float(credit_amount.text)

        total_sales_credit_value = round(total_sales_credit_value, 2)
        total_sales_credit_amount = round(total_sales_credit_amount, 2)
        sales_credit_difference = round(total_sales_credit_value - total_sales_credit_amount, 2)

        if abs(sales_credit_difference) > 0.02:
            errors.append({
                'status'  : 500,
                'response': "Sales Invoices Credit Amount Mismatch",
                'error'   : {
                    "Expected Total Credit (SalesInvoices)"  : total_sales_credit_value,
                    "Calculated Total Credit (SalesInvoices)": total_sales_credit_amount,
                    "Difference"                             : sales_credit_difference
                }
            })

        # validate Payments
        total_payment_credit = root.find(".//ns:Payments/ns:TotalCredit", namespace)
        total_payment_credit_value = float(total_payment_credit.text) if total_payment_credit is not None else 0.0

        total_payment_credit_amount = 0.0
        for payment in root.findall(".//ns:Payments/ns:Payment", namespace):
            payment_status = payment.find("ns:DocumentStatus/ns:PaymentStatus", namespace)

            for line in payment.findall(".//ns:Line", namespace):
                credit_amount = line.find("ns:CreditAmount", namespace)
                if credit_amount is not None and credit_amount.text and payment_status.text != "A":
                    total_payment_credit_amount += float(credit_amount.text)

        total_payment_credit_value = round(total_payment_credit_value, 2)
        total_payment_credit_amount = round(total_payment_credit_amount, 2)
        payment_credit_difference = round(total_payment_credit_value - total_payment_credit_amount, 2)

        if abs(payment_credit_difference) > 0.02:
            errors.append({
                'status'  : 500,
                'response': "Payments Credit Amount Mismatch",
                'error'   : {
                    "Expected Total Payment Credit"  : total_payment_credit_value,
                    "Calculated Total Payment Credit": total_payment_credit_amount,
                    "Difference"                     : payment_credit_difference
                }
            })

        return errors

    def query_validate_saft_debit_totals(self, xml):
        root = ET.fromstring(xml)
        namespace = {'ns': 'urn:OECD:StandardAuditFile-Tax:PT_1.04_01'}
        errors = []

        # Validate SalesInvoices Debit
        total_sales_debit = root.find(".//ns:SalesInvoices/ns:TotalDebit", namespace)
        total_sales_debit_value = float(total_sales_debit.text) if total_sales_debit is not None else 0.0

        total_sales_debit_amount = 0.0
        for invoice in root.findall(".//ns:SalesInvoices/ns:Invoice", namespace):
            invoice_type = invoice.find("ns:InvoiceType", namespace)
            invoice_status = invoice.find("ns:DocumentStatus/ns:InvoiceStatus", namespace)

            if invoice_type is None or invoice_status is None:
                continue

            if invoice_type.text in ["FT", "NC", "FR", "FS"] and invoice_status.text != "A":
                for line in invoice.findall(".//ns:Line", namespace):
                    debit_amount = line.find("ns:DebitAmount", namespace)
                    if debit_amount is not None and debit_amount.text:
                        total_sales_debit_amount += float(debit_amount.text)

        total_sales_debit_value = round(total_sales_debit_value, 2)
        total_sales_debit_amount = round(total_sales_debit_amount, 2)
        sales_debit_difference = round(total_sales_debit_value - total_sales_debit_amount, 2)

        if abs(sales_debit_difference) > 0.02:
            errors.append({
                'status'  : 500,
                'response': "Sales Invoices Debit Amount Mismatch",
                'error'   : {
                    "Expected Total Debit (SalesInvoices)"  : total_sales_debit_value,
                    "Calculated Total Debit (SalesInvoices)": total_sales_debit_amount,
                    "Difference"                            : sales_debit_difference
                }
            })

        return errors

    def query_validate_saft_payment_debit_totals(self, xml):
        """
        Validates SAFT payment debit totals from the provided XML.
        Ensures that: TotalDebit (Payments) = Sum of DebitAmount from payment lines
        Excludes annulled payments (PaymentStatus = 'A').
        Includes ALL currencies (line amounts already converted to EUR).
        Returns a list of discrepancies found.
        """
        root = ET.fromstring(xml)
        namespace = {"ns": "urn:OECD:StandardAuditFile-Tax:PT_1.04_01"}
        errors = []

        # Get TotalDebit from Payments section
        total_payment_debit = root.find(".//ns:Payments/ns:TotalDebit", namespace)
        total_payment_debit_value = (
            float(total_payment_debit.text)
            if total_payment_debit is not None
            else 0.0
        )

        # Sum DebitAmount from all payment lines (excluding annulled)
        total_payment_debit_amount = 0.0
        for payment in root.findall(".//ns:Payments/ns:Payment", namespace):
            payment_status = payment.find(
                "ns:DocumentStatus/ns:PaymentStatus", namespace
            )

            # Skip annulled payments
            if payment_status is not None and payment_status.text == "A":
                continue

            # Sum debit amounts from lines (all currencies included)
            for line in payment.findall(".//ns:Line", namespace):
                debit_amount = line.find("ns:DebitAmount", namespace)
                if debit_amount is not None and debit_amount.text:
                    total_payment_debit_amount += float(debit_amount.text)

        # Round values for comparison
        total_payment_debit_value = round(total_payment_debit_value, 2)
        total_payment_debit_amount = round(total_payment_debit_amount, 2)
        payment_debit_difference = round(
            total_payment_debit_value - total_payment_debit_amount, 2
        )

        # Check if difference exceeds tolerance
        if abs(payment_debit_difference) > 0.02:
            errors.append(
                {
                    "status"  : 500,
                    "response": "Payments Debit Amount Mismatch",
                    "error"   : {
                        "Expected Total Debit (Payments)"  : total_payment_debit_value,
                        "Calculated Total Debit (Payments)": total_payment_debit_amount,
                        "Difference"                       : payment_debit_difference,
                    },
                }
            )

        return errors

    def find_invoices_in_saft_xml(self, xml_content, invoice_numbers_list):
        """
        Search for specific invoice numbers in SAFT XML
        """
        root = ET.fromstring(xml_content)
        namespace = {"ns": "urn:OECD:StandardAuditFile-Tax:PT_1.04_01"}

        found_invoices = []
        xml_invoice_numbers = set()

        # Extract all invoice numbers from XML
        for invoice in root.findall(".//ns:SalesInvoices/ns:Invoice", namespace):
            invoice_type = invoice.find("ns:InvoiceType", namespace)
            invoice_status = invoice.find("ns:DocumentStatus/ns:InvoiceStatus", namespace)
            invoice_no = invoice.find("ns:InvoiceNo", namespace)

            # Filter using existing patterns: valid types and non-cancelled status
            if (invoice_type is not None
                    and invoice_status is not None
                    and invoice_no is not None
                    and invoice_type.text in ["FT", "NC", "FR", "FS"]
                    and invoice_status.text != "A"):
                xml_invoice_numbers.add(invoice_no.text)

        # Check which invoices from the search list are found
        for invoice_num in invoice_numbers_list:
            if invoice_num in xml_invoice_numbers:
                found_invoices.append(invoice_num)

        # Calculate missing invoices
        missing_invoices = [inv for inv in invoice_numbers_list if inv not in found_invoices]

        return {
            'found_invoices'  : found_invoices,
            'missing_invoices': missing_invoices
        }

    def get_date_mismatch_invoices(self, date_start, date_end, company_id):

        """
        Returns invoices created in current month but with validated_date from previous month
        """
        domain = [
            ('state', '=', 'posted'),
            ('company_id', '=', company_id.id),
            ('invoice_date', '<', date_start),  # set by user
            ('validated_date', '>=', date_start),  # created this month for sure
            ('inalterable_hash', '!=', False),
        ]
        invoices = request.env['account.move'].sudo().search(domain)
        problematic_invoices = []

        for invoice in invoices:
            problematic_invoices.append({
                'invoice_id'    : invoice.id,
                'invoice_name'  : invoice.name,
                'invoice_date'  : invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else None,
                'validated_date': invoice.validated_date.strftime('%Y-%m-%d') if invoice.validated_date else None,
                'partner_name'  : invoice.partner_id.name,
                'amount_total'  : invoice.amount_total,
            })

        return problematic_invoices

    def validate_cross_month_saft_invoices(self, current_saft_xml, date_start, date_end, company_id):
        """
        Validates that invoices created in CURRENT MONTH with PREVIOUS MONTH DATES
        are in PREVIOUS MONTHS SAFT and not in CURRENT MONTH SAFT

        :param current_saft_xml: Already generated SAFT XML for current month
        :param date_start: Current month start date
        :param date_end: Current month end date
        :param company_id: Company ID
        """
        errors = []

        # Get invoices with date mismatch (created in current month, validated_date from previous)
        problematic_invoices = self.get_date_mismatch_invoices(date_start, date_end, company_id)

        if not problematic_invoices:
            return []

        # Extract invoice numbers for search
        invoice_numbers = [inv['invoice_name'] for inv in problematic_invoices]

        # Get previous month date range
        prev_month_end = date_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)

        try:
            # Generate previous month SAFT only
            prev_saft_wiz = request.env["saft.wizard"].sudo().create({
                "date_start": prev_month_start,
                "date_end"  : prev_month_end,
                "company_id": company_id.id,
            })
            prev_saft_xml = prev_saft_wiz.sudo().with_context(
                lang=False, allowed_company_ids=[company_id.id]
            ).get_xml()
            prev_saft_wiz.unlink()

            # Check invoice presence in current month SAFT (should be empty)
            current_results = self.find_invoices_in_saft_xml(current_saft_xml, invoice_numbers)

            # Check invoice presence in previous month SAFT (should contain all)
            prev_results = self.find_invoices_in_saft_xml(prev_saft_xml, invoice_numbers)

            # Report errors for invoices incorrectly in current month SAFT
            if current_results['found_invoices']:
                errors.append({
                    "status"  : 500,
                    "response": "Cross-Month SAFT Validation Error",
                    "error"   : {
                        "message"               : "Invoices with previous month validated_date found in current month SAFT",
                        "invoices_in_wrong_saft": current_results['found_invoices'],
                        "invoice_details"       : [inv for inv in problematic_invoices
                                                   if inv['invoice_name'] in current_results['found_invoices']]
                    }
                })

            # Report errors for invoices missing from previous month SAFT
            if prev_results['missing_invoices']:
                errors.append({
                    "status"  : 500,
                    "response": "Cross-Month SAFT Validation Error",
                    "error"   : {
                        "message"                           : "Invoices with previous month validated_date missing from previous month SAFT",
                        "invoices_missing_from_correct_saft": prev_results['missing_invoices'],
                        "invoice_details"                   : [inv for inv in problematic_invoices
                                                               if
                                                               inv['invoice_name'] in prev_results['missing_invoices']]
                    }
                })

        except Exception as e:
            _logger.exception("Error validating cross-month SAFT invoices")
            errors.append({
                "status"  : 500,
                "response": "Cross-Month SAFT Validation Error",
                "error"   : {
                    "message"                  : "Exception during cross-month validation",
                    "exception"                : str(e),
                    "problematic_invoice_count": len(problematic_invoices)
                }
            })

        return errors

    def query_validate_proof_of_delivery(self, date_start, date_end, company_id):
        """
        Validates that if is_proof_delivery=True then shipping_departure_date must be filled
        """
        invoices = request.env['account.move'].sudo().search(
            [
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('invoice_date', '>=', date_start),
                ('invoice_date', '<=', date_end),
                ('company_id', '=', company_id.id),
                ('state', '=', 'posted'),
                ('is_proof_delivery', '=', True),
            ]
        )

        errors = []
        for inv in invoices:
            if not inv.shipping_departure_date:
                errors.append({
                    'invoice': inv.name,
                    'error'  : 'is_proof_delivery=True but shipping_departure_date is missing',
                })
        return errors

    def validate_request(self, post):
        """
        Validates the request for the required fields
        :param post:
        :return: None if the request is valid, otherwise a json response with proper error code and message
        """
        internal_api_key = request.env['ir.config_parameter'].sudo().get_param('arxi_saft_api_token')
        missing_fields = []

        if 'api_token' not in post or post.get('api_token') == "":
            return {
                'status'  : 401,
                'response': "Non-Authorized",
                'error:'  : "No Auth-Key.",
            }

        if not internal_api_key:
            return {
                'status'  : 401,
                'response': "Non-Authorized",
                'error:'  : "No Auth-Key stored on server.",
            }

        if post.get('api_token') != internal_api_key:
            return {
                'status'  : 401,
                'response': "Non-Authorized",
                'error:'  : "Provided key is different than the stored key.",
            }

        saft_data = post.get('saft_data')
        if saft_data is None:
            return {
                'status'        : 400,
                'response'      : "Missing required fields",
                'missing_fields': 'saft_data',
            }

        for field in REQUIRED_FIELDS:
            if field not in saft_data or saft_data.get(field) == "":
                missing_fields.append(field)

        if missing_fields:
            return {
                'status'        : 400,
                'response'      : "Missing required fields",
                'missing_fields': missing_fields,
            }

        return "OK"

    # Aux Methods
    def export_saft(self, date_end, date_start, company_id):
        """
        Exports the SAFT file based on the given date range
        :param date date_end:
        :param date date_start:
        :param res.company company_id:
        :return dict with the status, response and the xml file:
        """
        temp_wiz = request.env['saft.wizard'].sudo().create(
            {
                'date_start': date_start,
                'date_end'  : date_end,
                'company_id': company_id.id,
            })
        errors = []
        try:
            document = temp_wiz.sudo().with_context(lang=False, allowed_company_ids=[company_id.id]).get_xml()
            encoded_doc = base64.b64encode(
                b'<?xml version="1.0" encoding="Windows-1252"?>\n' + document.encode('Windows-1252'))
            result = temp_wiz.result
            result and result.replace('\n', '').replace(' ', '')
            state = temp_wiz.state
            rec_amount = self.get_amount_of_records(date_start, date_end, company_id)
            wiz_get_company_ids = temp_wiz.get_companies()
            temp_wiz.unlink()

            if state == 'error':
                errors.append(
                    {
                        'status'  : 422,
                        'response': "Error exporting SAFT from Odoo SAFT Wizard",
                        'error'   : result,
                    })

            if arr := self.query_validate_saft_payment_keys(document):
                errors.append(
                    {
                        'status'  : 500,
                        'response': "Payment Amount Mismatch",
                        'error'   : arr,
                    })
            if arr := self.query_validate_saft_credit_totals(document):
                errors.append(
                    {
                        'status'  : 500,
                        'response': "Sale Invoices Credit Amount Mismatch",
                        'error'   : arr,
                    })

            if arr := self.query_validate_saft_debit_totals(document):
                errors.append(
                    {
                        'status'  : 500,
                        'response': "Sale Invoices Debit Amount Mismatch",
                        'error'   : arr,
                    })

            if arr := self.query_validate_saft_payment_debit_totals(document):
                errors.append(
                    {
                        'status'  : 500,
                        'response': "Payments Debit Amount Mismatch",
                        'error'   : arr,
                    })

            if validation_err := self.query_validate_saft_stock_move_keys(document, date_start, date_end,
                                                                          wiz_get_company_ids):
                errors.append(
                    {
                        'status'  : 500,
                        'response': "Stock Move Mismatch",
                        'error'   : validation_err,
                    })

            # Validate cross-month invoice placement
            if cross_month_errors := self.validate_cross_month_saft_invoices(
                    document, date_start, date_end, company_id
            ):
                errors.extend(cross_month_errors)

            if arr := self.query_validate_proof_of_delivery(date_start, date_end, company_id):
                errors.append(
                    {
                        'status'  : 500,
                        'response': "Proof of Delivery Validation Error",
                        'error'   : arr,
                    })

            if errors:
                return {
                    'status'               : 500,
                    'response'             : "Multiple Errors Exporting SAFT",
                    'company_id'           : company_id.id,
                    'company_name'         : company_id.name,
                    'error'                : errors,
                    'record_amount_total'  : rec_amount.get('total'),
                    'record_amount_details': rec_amount.get('amount_data'),
                    'xml'                  : document,
                    'encoded_doc'          : encoded_doc,
                }

            else:
                return {
                    'status'               : 200,
                    'response'             : "Success",
                    'company_id'           : company_id.id,
                    'company_name'         : company_id.name,
                    'record_amount_total'  : rec_amount.get('total'),
                    'record_amount_details': rec_amount.get('amount_data'),
                    'xml'                  : document,
                    'encoded_doc'          : encoded_doc,
                }

        except Exception as e:
            _logger.exception(e)
            error_message = traceback.format_exc()
            return {
                'status'               : 500,
                'response'             : "Odoo error exporting SAFT",
                'company_id'           : company_id and company_id.id or 0,
                'company_name'         : company_id and company_id.name or "None",
                'error'                : f"{str(e)} - {error_message}",
                'record_amount_total'  : 0,
                'record_amount_details': [],
            }

    def get_amount_of_records(self, date_start, date_end, company_id):
        """
        Returns the amount of records created between the given dates
        :param date date_start:
        :param date date_end:
        :param res.company company_id:
        :return dict with the amount of records per model + total:
        """
        domain = [('create_date', '>=', date_start), ('create_date', '<=', date_end),
                  ('company_id', '=', company_id.id)]
        orders = request.env['sale.order'].sudo().search(domain)
        order_lines = request.env['sale.order.line'].sudo().search(domain)
        invoices = request.env['account.move'].sudo().search(domain)
        invoice_lines = request.env['account.move.line'].sudo().search(domain)
        products = request.env['product.product'].sudo().search(domain)
        partners = request.env['res.partner'].sudo().search(domain)
        taxes = request.env['account.tax'].sudo().search(domain)
        journals = request.env['account.journal'].sudo().search(domain)
        payments = request.env['account.payment'].sudo().search(domain)
        # transport_docs = request.env['pt.transport'].sudo().search(domain) # TODO: some clients do not have this installed. Find a way to conditionally search for this value.
        total = len(orders) + len(order_lines) + len(invoices) + len(invoice_lines) + len(products) + len(
            partners) + len(taxes) + len(journals) + len(payments)

        return {
            'total'      : total,
            'amount_data': {
                'orders'       : len(orders),
                'order_lines'  : len(order_lines),
                'invoices'     : len(invoices),
                'invoice_lines': len(invoice_lines),
                'products'     : len(products),
                'partners'     : len(partners),
                'taxes'        : len(taxes),
                'journals'     : len(journals),
                'payments'     : len(payments),
            }
        }
