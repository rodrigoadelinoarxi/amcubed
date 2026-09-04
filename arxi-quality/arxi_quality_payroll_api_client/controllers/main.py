import base64
import logging
import traceback
from datetime import datetime

from odoo import http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)
REQUIRED_FIELDS = [
    'export_type',
    'date_start',
    'date_end',
]


class ArxiQualityPayrollApiClient(AuthSignupHome):
    _webhook_url = '/export/payroll'

    @http.route(_webhook_url, type='json', auth='none', methods=['POST'], csrf=False)
    def get_payroll_response(self, **post):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url'),
        # TODO use the above base_url to fetch the ir.attatchment id that comes from the execute methods to properly validate the file in the next phase
        current_company_id = False
        company_ids = False
        arr = []
        err_arr = []
        try:
            res = self.validate_request(post)
            if res != "OK":
                return res
            payroll_data = post.get('payroll_data')
            date_start = datetime.strptime(payroll_data.get('date_start'), "%Y-%m-%d").date()
            date_end = datetime.strptime(payroll_data.get('date_end'), "%Y-%m-%d").date()
            company_ids = request.env['res.company'].sudo().search([], order='id asc')

            for company_id in company_ids:
                domain = [('company_id', '=', company_id.id),
                          ('date_from', '>=', date_start)]
                if payslips := request.env['hr.payslip'].sudo().search(domain):
                    current_company_id = company_id
                    wiz_dmr = request.env['export.dmr.wizard'].sudo().create({
                        'date_start'          : date_start,
                        'date_end'            : date_end,
                        'is_first_declaration': True,
                        'art_119'             : True,
                    })
                    result_dmr = wiz_dmr.with_company(company_id).execute()
                    dmr_arr = {
                        'company'    : company_id.name,
                        'export_type': 'DMR',
                        'result'     : result_dmr,
                    }
                    arr.append(dmr_arr)

                    wiz_dri = request.env['export.dri.wizard'].sudo().create({
                        'date_start': date_start,
                        'date_end'  : date_end,
                    })
                    result_dir = wiz_dri.with_company(company_id).execute()
                    dri_arr = {
                        'company'    : company_id.name,
                        'export_type': 'DRI',
                        'result'     : result_dir,
                    }
                    arr.append(dri_arr)
                    wiz_insurance_map = request.env['export.insurance.map.wizard'].sudo().create({
                        'date_start'   : date_start,
                        'date_end'     : date_end,
                        'policy_number': company_id.insurance_policy_number,
                    })
                    result_insurance_map = wiz_insurance_map.with_company(company_id).execute()
                    insurance_map_arr = {
                        'company'    : company_id.name,
                        'export_type': 'Insurance Map',
                        'result'     : result_insurance_map,
                    }
                    arr.append(insurance_map_arr)

                    # unlink wizards
                    wiz_dmr.unlink()
                    wiz_dri.unlink()
                    wiz_insurance_map.unlink()

            return [{
                'status'     : 200,
                'response'   : "Ok",
                'company_arr': company_ids,
                'result_arr' : arr,
            }]

        except Exception as e:
            error_message = traceback.format_exc()
            error_data = {
                'company': current_company_id and current_company_id.name or "None",
                'vat'    : current_company_id and current_company_id.vat or "None",
                'message': str(e),
                'error'  : error_message,
            }
            err_arr.append(error_data)

        if err_arr:
            return [{
                'status'     : 500,
                'response'   : "Error",
                'company_arr': company_ids,
                'error_arr'  : err_arr,
                'success_arr': arr,
            }]

    def validate_request(self, post):
        """
        Validates the request for the required fields
        :param post:
        :return: None if the request is valid, otherwise a json response with proper error code and message
        """
        internal_api_key = request.env['ir.config_parameter'].sudo().get_param('arxi_payroll_api_token')
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

        payroll_data = post.get('payroll_data')
        if payroll_data is None:
            return {
                'status'        : 400,
                'response'      : "Missing required fields",
                'missing_fields': 'payroll_data',
            }

        if missing_fields:
            return {
                'status'        : 400,
                'response'      : "Missing required fields",
                'missing_fields': missing_fields,
            }

        return "OK"
