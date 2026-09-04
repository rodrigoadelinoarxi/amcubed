import base64
import logging
import math

from dateutil.relativedelta import relativedelta

from odoo import models, fields, _, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round

_logger = logging.getLogger(__name__)


class ExportDMR(models.TransientModel):
    _name = 'export.dmr.wizard'
    _description = 'Wizard to export DMR File'

    date_start = fields.Date(
        string='Start Date',
        default=fields.Date.today().replace(month=fields.Date.today().month, day=1) - relativedelta(months=1))
    date_end = fields.Date(
        string='End Date',
        default=fields.Date.today().replace(day=1) - relativedelta(days=1))

    is_first_declaration = fields.Boolean(string="Is First Declaration", default=True)

    art_119 = fields.Boolean(string="Declaration presented pursuant to art. d), no. 1, art. 119", default=False)

    changes_date = fields.Date(string="Changes Date", default=False)

    fair_impediment = fields.Boolean(string="Fair Impediment", default=False)

    fair_impediment_reason = fields.Selection([
        ('01',
         'Death of a spouse not separated from persons and property, of a person with whom live in conditions similar to those of spouses, or relatives or similar in the 1st degree of the straight line.'),
        ('02',
         'Death of another relative or related person in the direct line or in the 2nd degree of the collateral line.'),
        ('03',
         'Serious and sudden illness or hospitalization of the accountant, which makes it impossible to absolute ability to fulfill their obligations, or situations of childbirth or urgent assistance and essential for the spouse or person living in a de facto union or common economy and the relative or similar in the 1st degree of the straight line, in case of illness or accident.'),
        ('04', 'Parenting Situations.'),
    ])

    fair_impediment_date = fields.Date(string="Fair Impediment Date")

    fair_impediment_date_end = fields.Date(string="Fair Impediment End Date")

    line_count = fields.Integer()

    @api.onchange('date_start')
    def onchange_date_start(self):
        """
        When changing the start date, automatically put the end date at the end of the month.
        :return:
        """
        if self.date_start:
            self.date_end = self.date_start + relativedelta(months=1, days=-1)

    def _get_payslips_lines(self):
        lines = []
        payslips = self.env['hr.payslip'].search([('date_to', '<=', self.date_end), ('state', 'in', ['done', 'paid'])]).filtered(lambda slip: slip.date_to.year == self.date_end.year)
        for payslip in payslips:
            if payslip.date_to.month != self.date_start.month:
                continue
            for line in payslip.line_ids:
                if not line.employee_id.contrib_entity:
                    raise ValidationError(
                        _('An employee has no Contribution Entity selected: %s', line.employee_id.name))
                if not line.employee_id.birthday:
                    raise ValidationError(_(f'An employee has no birthday: %s', line.employee_id.name))
                if not line.employee_id.ssnid:
                    raise ValidationError(_(f'An employee has no Social Security Number: %s', line.employee_id.name))
                if not line.employee_id.fiscal_number:
                    raise ValidationError(_(f'An employee has no Fiscal Number: %s', line.employee_id.name))
                lines.append(line)
        return lines

    def _add_spaces_to_register(self, register):
        while len(register) < 172:
            register += " "
        register += "\n"
        return register

    def _format_lines(self, line, length):
        sig = "+"
        zeros = ""
        len_line = len(line)
        if '-' in line:
            line = line.replace('-', '')
            len_line = len(line)
            sig = '-'
        while len_line < length:
            zeros += "0"
            len_line += 1
        line = sig + zeros + line
        return line

    # ---------------------FILE HEADER----------------------
    def _get_file_header(self):
        register_type = "001"
        file_type = "ASCII"
        file_version = "05"
        file_date = fields.Date.today().strftime('%Y%m%d')

        file_header = register_type + file_type + file_version + file_date
        file_header = self._add_spaces_to_register(file_header)
        return file_header.encode('utf-8')

    # ---------------------DECLARATION HEADER---------------------
    def _get_declaration_header(self):
        register_number = "002"
        declaration_type = "DMR-AT"
        nif = self.env.company.vat.replace('PT', '')
        year = str(self.date_end.strftime('%Y'))
        month = str(self.date_end.strftime('%m'))
        currency = "EUR"
        dec_header = register_number + declaration_type + nif + year + month + currency
        dec_header = self._add_spaces_to_register(dec_header)
        return dec_header.encode('utf-8')

    # -------------------DMT-AT HEADER--------------------
    def _get_dmr_header(self):
        reg_type = "003"
        at_code = self._get_company_finance_code()
        is_first_dec = "1" if self.is_first_declaration else "2"
        art_119 = "3" if self.art_119 else "0"
        changes_date = self._get_changes_date()
        accountant_nif = self._get_company_certified_accountant()
        legal_rep_nif = self._get_company_legal_representant()
        fair_impediment_reason = self._get_fair_impediment_reason()
        fair_impediment_date = self._get_fair_impediment_date()
        fair_impediment_date_end = self._get_fair_impediment_date_end()

        dmr_header = reg_type + at_code + is_first_dec + art_119 + changes_date + accountant_nif + legal_rep_nif + fair_impediment_reason + fair_impediment_date + fair_impediment_date_end
        dmr_header = self._add_spaces_to_register(dmr_header)
        return dmr_header.encode('utf-8')

    def _get_fair_impediment_reason(self):
        if self.fair_impediment and self.fair_impediment_reason:
            return self.fair_impediment_reason
        elif self.fair_impediment and not self.fair_impediment_reason:
            raise UserError(_('You need to select a Fair Impediment Reason'))
        else:
            return "  "

    def _get_fair_impediment_date(self):
        if self.fair_impediment and self.fair_impediment_date:
            return self.fair_impediment_date.strftime('%Y%m%d')
        elif self.fair_impediment and not self.fair_impediment_date:
            raise UserError(_('You need to select the date of the Fair Impediment'))
        else:
            return "00000000"

    def _get_fair_impediment_date_end(self):
        if self.fair_impediment_date_end:
            return self.fair_impediment_date_end.strftime('%Y%m%d')
        elif self.fair_impediment_reason == '03' and not self.fair_impediment_date_end:
            raise UserError(_('You need to select the date of the end of the Fair Impediment'))
        else:
            return "00000000"

    def _get_company_finance_code(self):
        return self.env.company.finance_service_code

    def _get_company_legal_representant(self):
        return self.env.company.legal_rep_nif

    def _get_company_certified_accountant(self):
        return self.env.company.accountant_nif

    def _get_changes_date(self):
        if self.changes_date:
            return self.changes_date.strftime('%Y%m%d')
        else:
            return "00000000"

    # ------------------DMR AT.1 DETAIL--------------------
    def _get_dmr_at_1_detail(self):
        reg_type = "004"
        income_value = self._get_income_subject_to_irs()  # soma dos rendimentos sujeitos a irs
        irs_retention = self._get_irs_retention(size=14)
        required_contribuitions = self._get_required_contributions()
        union_quotes_subject_to_irs = self._get_union_quotes_subject_to_irs()
        overtax_retention_subject_to_irs = self._get_overtax_retention_subject_to_irs()
        exempt_income = self._get_exempt_income()
        exempt_income_irs_retention = self._get_exempt_income_irs_retention()
        exempt_income_required_contribuitions = self._get_exempt_income_required_contribuitions()
        exempt_income_union_quotes = self._get_exempt_income_union_quotes()
        exempt_income_overtax_retention = self._get_exempt_income_overtax_retention()
        dmr_at_1_detail = reg_type + income_value + irs_retention + required_contribuitions + union_quotes_subject_to_irs + overtax_retention_subject_to_irs + exempt_income + exempt_income_irs_retention + exempt_income_required_contribuitions + exempt_income_union_quotes + exempt_income_overtax_retention
        dmr_at_1_detail = self._add_spaces_to_register(dmr_at_1_detail)
        return dmr_at_1_detail.encode('utf-8')

    def _get_income_subject_to_irs(self):
        total = 0
        non_subject_total = 0
        ded_total = 0  # NEW: Track DED amounts

        grouped_content = self.prepare_get_dmr_at_3_detail()
        for key, line in grouped_content.items():
            if line.get('lines'):
                for slip_line in line.get('lines'):
                    if slip_line.salary_rule_id.category_id.code == 'IRS':
                        current_year_income = line.get('current_year_income')
                        line['current_year_income'] = current_year_income
                    # NEW: Track DED amounts for income type 'A' (only if income_type is defined)
                    elif slip_line.salary_rule_id.category_id.code == 'DED' and slip_line.salary_rule_id.income_type and line.get('income_type').strip() == 'A':
                        ded_total += slip_line.total

            if line.get('income_type').strip() in ['A20', 'A21', 'A22', 'A23', 'A24', 'A25', 'A26', 'A30', 'A31', 'A32',
                                                   'A33', 'A40', 'A82']:
                non_subject_total += int(line.get('current_year_income')) / 100

            total += int(line.get('current_year_income')) / 100

        total = total - non_subject_total  # Original logic
        # Note: If using SOLUTION 1, DED is already subtracted in grouped_lines
        # If not using SOLUTION 1, uncomment the next line:
        # total = total - ded_total  # NEW: Subtract DED amounts

        total = float_round(total, 2)
        if total > 0:
            total = str(int(float_round(total * 100, 2)))
            total = self._format_lines(total, 15)
            return total
        else:
            return "+000000000000000"

    def _get_irs_retention(self, size=15):
        irs_retention = 0
        lines = self._get_payslips_lines()
        for line in lines:
            if line.salary_rule_id.code in ['IRSVM', 'IRSVACSUB', 'IRSCHRSUB', 'IRSMEALSUB']:
                # Don't round individual lines - sum exact values
                irs_retention += line.total
        if irs_retention > 0:
            # Only round the total
            irs_retention = float_round(irs_retention, 2)
            irs_retention = str(int(irs_retention * 100))
            irs_retention = str(irs_retention).replace('.', '')
            irs_retention = self._format_lines(irs_retention, size)
        else:
            return size == 15 and "+000000000000000" or "+00000000000000"
        return irs_retention

    def _get_required_contributions(self, size=14):
        required_contribuitions = 0
        grouped_content = self.prepare_get_dmr_at_3_detail()
        for key, line in grouped_content.items():
            current_year_income = line.get('current_year_income')
            if line.get('income_type').strip() in ['A', 'A2', 'A3', 'A4', 'A5', 'A61', 'A62', 'A63', 'A64', 'A65',
                                                   'A66', 'A67', 'A68']:
                if line.get('lines'):
                    not_subject = 0
                    for slip_line in line.get('lines'):
                        ss_rate = slip_line.slip_id.version_id.ss_regime.employee_rate
                        if not slip_line.salary_rule_id.ss_code and slip_line.salary_rule_id.income_type and slip_line.salary_rule_id.category_id.code not in [
                            'IRS', 'SA']:
                            not_subject += slip_line.total
                        income = float_round((int(current_year_income) / 100), 2) - not_subject
                        required_contribution_line = self._get_required_contributions_per_line_new(income, ss_rate)
                else:
                    for slip_line in line.get('lines'):
                        ss_rate = slip_line.slip_id.version_id.ss_regime.employee_rate
                        if (slip_line.salary_rule_id.category_id.code in ['IRS',
                                                                          'SA'] and slip_line.total > 0) or slip_line.salary_rule_id.category_id.code in [
                            'VACSUB', 'CHRSUB']:
                            required_contribution_line = self._get_required_contributions_per_line_new(slip_line.amount, ss_rate)
                required_contribuitions += int(required_contribution_line) / 100
        if required_contribuitions > 0:
            required_contribuitions = str(int(float_round(required_contribuitions, 2) * 100))
            required_contribuitions = self._format_lines(required_contribuitions, size)
        else:
            return size == 14 and "+00000000000000" or "+000000000000000"
        return required_contribuitions

    def _get_union_quotes_subject_to_irs(self):
        union_quotes = 0
        lines = self._get_payslips_lines()
        for line in lines:
            if line.salary_rule_id.code == 'UNION':
                union_quotes += line.total
        if union_quotes > 0:
            union_quotes = round(union_quotes, 2)
            union_quotes = str(union_quotes).replace('.', '')
            union_quotes = self._format_lines(union_quotes, 14)
        else:
            return "+00000000000000"
        return union_quotes

    def _get_overtax_retention_subject_to_irs(self):
        # para já devolve só zeros
        return "+00000000000000"

    def _get_exempt_income(self):
        exempt_income = 0
        lines = self._get_payslips_lines()
        for line in lines:
            if line.salary_rule_id.category_id.code == 'BONUS':
                exempt_income += line.total
            if line.salary_rule_id.category_id.code == 'PERF_BONUS':
                wage = line.slip_id.version_id.wage
                exempt_income = wage * 0.06
        if exempt_income > 0:
            exempt_income = str(int(float_round(exempt_income, 2) * 100))
            exempt_income = str(exempt_income).replace('.', '')
            exempt_income = self._format_lines(exempt_income, 15)
        else:
            return "+000000000000000"
        return exempt_income

    def _get_exempt_income_irs_retention(self):
        # always zero
        return "+00000000000000"

    def _get_exempt_income_required_contribuitions(self):
        # always zero
        return "+00000000000000"

    def _get_exempt_income_union_quotes(self):
        # always zero
        return "+00000000000000"

    def _get_exempt_income_overtax_retention(self):
        # always zero
        return "+00000000000000"

    # -----------------DMR-AT.2 DETAIL--------------------
    def _get_dmr_at_2_detail(self):
        reg_type = "005"
        not_subject_income = self._get_not_subject_income()
        income_value = self._get_income_subject_to_irs()
        not_subject_income_retention_irs = self._get_not_subject_income_retention_irs()
        not_subject_income_required_contribuitions = self._get_not_subject_income_required_contribuitions()
        not_subject_income_union_quotes = self._get_not_subject_income_union_quotes()
        not_subject_income_overtax_retention = self._get_not_subject_income_overtax_retention()
        exempt_income = self._get_total_exempt_income()
        total_income = self._sum_formatted_total_income(income_value, not_subject_income, exempt_income)
        total_irs_retention = self._get_irs_retention()
        total_required_contributions = self._get_required_contributions(size=15)
        total_union_quotes = self._get_total_union_quotes()
        total_overtax_retention = self._get_total_overtax_retention()
        dmr_at_2_detail = reg_type + not_subject_income + not_subject_income_retention_irs + not_subject_income_required_contribuitions + not_subject_income_union_quotes + not_subject_income_overtax_retention + total_income + total_irs_retention + total_required_contributions + total_union_quotes + total_overtax_retention
        dmr_at_2_detail = self._add_spaces_to_register(dmr_at_2_detail)
        return dmr_at_2_detail.encode('utf-8')

    def _get_not_subject_income(self):
        total = 0
        grouped_content = self.prepare_get_dmr_at_3_detail()
        for key, line in grouped_content.items():
            if line.get('income_type').strip() in ['A20', 'A21', 'A22', 'A23', 'A24', 'A25', 'A26', 'A30', 'A31', 'A32',
                                                   'A33']:
                total += int(line.get('current_year_income')) / 100
        if total > 0:
            total = str(int(float_round(total * 100, 2)))
            total = self._format_lines(total, 15)
        else:
            return "+000000000000000"
        return total

    def _get_total_exempt_income(self):
        total = 0
        grouped_content = self.prepare_get_dmr_at_3_detail()
        for key, line in grouped_content.items():
            if line.get('income_type').strip() in ['A40']:
                total += int(line.get('current_year_income')) / 100
        return total

    def _get_not_subject_income_retention_irs(self):
        # always zero
        return "+00000000000000"

    def _get_not_subject_income_required_contribuitions(self):
        # always zero
        return "+00000000000000"

    def _get_not_subject_income_union_quotes(self):
        # always zero
        return "+00000000000000"

    def _get_not_subject_income_overtax_retention(self):
        # always zero
        return "+00000000000000"

    def taxed_value_meal_allowance_subject_value(self, contract, payslip):
        taxed_value = 0
        company = payslip.company_id

        if contract.food == 'cartao':
            exempt_limit = company.default_hr_payroll_food_val_card_exempt_limit or 0
            # Use the lower value between foodValue and exempt limit (EXEMPT portion)
            taxed_value = min(contract.foodValue, exempt_limit)
        elif contract.food == 'normal':
            exempt_limit = company.default_hr_payroll_food_val_exempt_limit or 0
            # Use the lower value between foodValue and exempt limit (EXEMPT portion)
            taxed_value = min(contract.foodValue, exempt_limit)

        total = taxed_value * payslip.meal_allw_days
        return total

    def taxed_value_meal_allowance_subject(self, contract, payslip):
        total = self.taxed_value_meal_allowance_subject_value(contract, payslip)
        total = str(int(total * 100))
        formatted_total = str(total).replace('.', '')
        return self._format_lines(formatted_total, 14)

    def taxed_value_meal_allowance_exempt_value(self, contract, payslip):
        taxed_value = 0
        company = payslip.company_id

        if contract.food == 'cartao':
            exempt_limit = company.default_hr_payroll_food_val_card_exempt_limit or 0
            # Calculate TAXABLE amount (above exemption limit)
            if contract.foodValue > exempt_limit:
                taxed_value = contract.foodValue - exempt_limit
        elif contract.food == 'normal':
            exempt_limit = company.default_hr_payroll_food_val_exempt_limit or 0
            # Calculate TAXABLE amount (above exemption limit)
            if contract.foodValue > exempt_limit:
                taxed_value = contract.foodValue - exempt_limit

        total = taxed_value * payslip.meal_allw_days
        return float(total)

    def taxed_value_meal_allowance_exempt(self, contract, payslip):
        total = self.taxed_value_meal_allowance_exempt_value(contract, payslip)
        formatted_total = str(int(total * 100))
        formatted_total = str(formatted_total).replace('.', '')
        return self._format_lines(formatted_total, 14)

    def exempt_value(self, value, input_value):
        total = float_round(value * input_value, 2)
        formatted_total = str(int(total * 100))
        formatted_total = str(formatted_total).replace('.', '')
        return self._format_lines(formatted_total, 14)

    def perf_bonus_exempt_value(self, wage):
        total = wage * 0.06
        formatted_total = str(int(total * 100))
        formatted_total = str(formatted_total).replace('.', '')
        return self._format_lines(formatted_total, 14)

    def perf_bonus_subject_value(self, wage, amount):
        exempt = wage * 0.06
        total = amount - exempt
        return total

    def taxed_value_fail_allow_exempt_value(self, wage):
        exempt_value = ((wage * 14) / 12) * 0.05
        return round(exempt_value, 2)

    def taxed_value_fail_allow_exempt(self, wage):
        total = self.taxed_value_fail_allow_exempt_value(wage)
        total = str(int(total * 100))
        total = str(total).replace('.', '')
        total = self._format_lines(total, 14)
        return total

    def taxed_value_fail_allow_subject_value(self, wage, amount):
        taxed_amount = 0
        exempt_value = ((wage * 14) / 12) * 0.05
        taxed_amount += amount - exempt_value
        return float_round(taxed_amount, 2)

    def taxed_value_fail_allow_subject(self, wage, amount):
        total = self.taxed_value_fail_allow_subject_value(wage, amount)
        total = str(int(total * 100))
        total = str(total).replace('.', '')
        total = self._format_lines(total, 14)
        return total

    def _sum_formatted_total_income(self, subject_income, non_subject_income, exempt_income):
        subject_income = int(subject_income) / 100
        non_subject_income = int(non_subject_income) / 100
        total = subject_income + non_subject_income + exempt_income
        total = str(int(float_round((total * 100), 2)))
        total = str(total).replace('.', '')
        total = self._format_lines(total, 16)
        return total

    def _get_total_union_quotes(self):
        subject_union_quotes = float(self._get_union_quotes_subject_to_irs())
        exempt_union_quotes = float(self._get_exempt_income_union_quotes())
        not_subject_union_quotes = float(self._get_not_subject_income_union_quotes())
        total = subject_union_quotes + exempt_union_quotes + not_subject_union_quotes
        if total > 0:
            total = round(total, 2)
            total = str(total).replace('.', '')
            total = self._format_lines(total, 15)
        else:
            return "+000000000000000"
        return total

    def _get_total_overtax_retention(self):
        subject_overtax_retention = float(self._get_overtax_retention_subject_to_irs())
        exempt_overtax_retention = float(self._get_exempt_income_overtax_retention())
        not_subject_overtax_retention = float(self._get_not_subject_income_overtax_retention())
        total = subject_overtax_retention + exempt_overtax_retention + not_subject_overtax_retention
        if total > 0:
            total = float_round(total, 2)
            total = str(total).replace('.', '')
            total = self._format_lines(total, 15)
        else:
            return "+000000000000000"
        return total

    # ----------------------- DMR AT.3 DETAIL-------------------------

    def sum_with_padding(self, val1, val2):
        standard_size = len(val1.replace('+', ''))
        clean_val1 = val1.replace('+', '')
        if '-' in val1:
            clean_val1 = int(clean_val1.replace('-', '')) * -1
        else:
            clean_val1 = int(clean_val1)
        clean_val2 = val2.replace('+', '')
        if '-' in val2:
            clean_val2 = int(clean_val2.replace('-', '')) * -1
        else:
            clean_val2 = int(clean_val2)
        sum = clean_val1 + clean_val2
        return self._format_lines(str(sum), standard_size)

    def prepare_exempt_income_type_line(self, line, grouped_lines):
        employee_nif = str(line.employee_id.fiscal_number)
        income_type = self._get_income_type_line(line, line.salary_rule_id.exempt_income_type)
        income_locale = self._get_income_locale(line)
        previous_years_income = self._get_previous_years_income(line.employee_id)
        previous_years_income_year = self._get_previous_years_income_year(line.employee_id)
        if line.category_id.code == 'FAIL_ALLOW':
            wage_line = line.slip_id.line_ids.filtered(lambda x: x.category_id.code == 'BASIC')
            if not wage_line:
                raise ValidationError(
                    _('No Wage was found for Slip %s.' % line.slip_id.name))
            current_year_income = self.taxed_value_fail_allow_exempt(wage_line[0].total)
            if line.total <= self.taxed_value_fail_allow_exempt_value(wage_line[0].total):
                current_year_income = line.total
                current_year_income = str(int(current_year_income * 100))
                current_year_income = str(current_year_income).replace('.', '')
                current_year_income = self._format_lines(current_year_income, 14)
        elif line.category_id.code == 'SA':
            current_year_income = self.taxed_value_meal_allowance_subject(line.slip_id.version_id, line.slip_id)
        elif line.category_id.code == 'KMS':
            exempt_value = 0.4
            input_value = line.slip_id.input_line_ids.filtered(
                lambda l: l.input_type_id == self.env.ref('l10n_pt_hr_payroll.hr_rule_input_km')).amount
            current_year_income = self.exempt_value(exempt_value, input_value)
        elif line.category_id.code == 'PERF_BONUS':
            wage = line.slip_id.version_id.wage
            current_year_income = self.perf_bonus_exempt_value(wage)
        elif line.category_id.code == 'COST_ALLW':
            exempt_value = self.env.company.default_hr_payroll_cost_allowance_exempt_limit if not line.employee_id.moe else self.env.company.default_hr_payroll_cost_allowance_moe_exempt_limit
            exempt_value = line.slip_id.version_id.cost_allw_amount if line.slip_id.version_id.cost_allw_amount <= exempt_value else exempt_value
            input_value = line.slip_id.input_line_ids.filtered(
                lambda l: l.input_type_id == self.env.ref('l10n_pt_hr_payroll.hr_rule_input_ac')).amount
            current_year_income = self.exempt_value(exempt_value, input_value)
        elif line.category_id.code == 'AC_FOREIGN':
            exempt_value = self.env.company.default_hr_payroll_foreign_cost_allowance_moe_exempt_limit if line.employee_id.moe else self.env.company.default_hr_payroll_foreign_cost_allowance_exempt_limit
            exempt_value = line.slip_id.version_id.cost_allw_amount_foreign if line.slip_id.version_id.cost_allw_amount_foreign <= exempt_value else exempt_value
            input_value = line.slip_id.input_line_ids.filtered(
                lambda l: l.input_type_id == self.env.ref('l10n_pt_hr_payroll.hr_rule_input_ac_foreign')).amount
            current_year_income = self.exempt_value(exempt_value, input_value)
        elif line.category_id.code == 'TERM_COMP':
            first_contract_year = line.slip_id.employee_id._l10n_pt_get_first_contract_year() or line.slip_id.date_from.year
            antiguity = line.slip_id.date_from.year - first_contract_year
            antiguity = antiguity if antiguity > 0 else 1
            slips = line.env['hr.payslip'].search(
                [('employee_id', '=', line.slip_id.employee_id.id), ('state', 'in', ['done', 'paid'])]).filtered(
                lambda s: s.date_from >= line.slip_id.date_from + relativedelta(years=-1))
            slips -= line.slip_id
            cat_a_total = 0
            for slip in slips:
                for li in slip.line_ids.filtered(lambda l: l.salary_rule_id.category_id.code == 'BASIC'):
                    cat_a_total += li.total
            limit_value = ((cat_a_total * antiguity) / 12)

            exempt_value = line.total - limit_value if line.total - limit_value > 0 else 0
            current_year_income = self.exempt_value(1, exempt_value)
        else:
            current_year_income = self.exempt_value(1, line.total)
        irs_retention = self._get_irs_retention_per_line(line)
        required_contribution_entity_1 = self._get_required_contribution_entity_1(line)
        required_contribution_entity_2 = self._get_required_contribution_entity_2(line)
        required_contribution_entity_3 = self._get_required_contribution_entity_3(line)
        union_quotes_line = self._get_union_quotes_line(line)
        overtax_retention_line = self._get_overtax_retention_line(line)
        grouping_field = employee_nif + income_type + income_locale
        if grouping_field in grouped_lines:
            grouped_lines[grouping_field]['current_year_income'] = self.sum_with_padding(
                grouped_lines[grouping_field]['current_year_income'], current_year_income)
            grouped_lines[grouping_field]['irs_retention'] = self.sum_with_padding(
                grouped_lines[grouping_field]['irs_retention'], irs_retention)
            grouped_lines[grouping_field]['lines'] |= line
        else:
            grouped_lines[grouping_field] = {
                'employee_nif'                  : employee_nif,
                'income_type'                   : income_type,
                'income_locale'                 : income_locale,
                'previous_years_income'         : previous_years_income,
                'previous_years_income_year'    : previous_years_income_year,
                'current_year_income'           : current_year_income,
                'irs_retention'                 : irs_retention,
                'required_contribution_entity_1': required_contribution_entity_1,
                'required_contribution_entity_2': required_contribution_entity_2,
                'required_contribution_entity_3': required_contribution_entity_3,
                'union_quotes_line'             : union_quotes_line,
                'overtax_retention_line'        : overtax_retention_line,
                'category_code'                 : line.salary_rule_id.category_id.code,
                'lines'                         : line
            }

    def prepare_get_dmr_at_3_detail(self):
        grouped_lines = {}

        # First, process all non-DED lines as before
        for line in self._get_payslips_lines():
            if line.salary_rule_id.category_id.code not in ['DED', 'GROSS', 'NET']:
                if line.salary_rule_id.exempt_income_type:
                    self.prepare_exempt_income_type_line(line, grouped_lines)
                # Special handling for SA (meal allowance) - split into exempt (A21) and taxable (A)
                if line.salary_rule_id.category_id.code == 'SA' and line.salary_rule_id.income_type:
                    # Process exempt portion (A21 or income_type from rule)
                    employee_nif = str(line.employee_id.fiscal_number)
                    income_type = self._get_income_type_line(line)  # Use the income_type from rule (A21)
                    income_locale = self._get_income_locale(line)
                    previous_years_income = self._get_previous_years_income(line.employee_id)
                    previous_years_income_year = self._get_previous_years_income_year(line.employee_id)
                    # Calculate EXEMPT amount
                    exempt_amount = self.taxed_value_meal_allowance_subject_value(line.slip_id.version_id, line.slip_id)
                    current_year_income = str(int(exempt_amount * 100))
                    current_year_income = str(current_year_income).replace('.', '')
                    current_year_income = self._format_lines(current_year_income, 14)
                    irs_retention = self._get_irs_retention_per_line(line)
                    required_contribution_entity_1 = self._get_required_contribution_entity_1(line)
                    required_contribution_entity_2 = self._get_required_contribution_entity_2(line)
                    required_contribution_entity_3 = self._get_required_contribution_entity_3(line)
                    union_quotes_line = self._get_union_quotes_line(line)
                    overtax_retention_line = self._get_overtax_retention_line(line)
                    grouping_field = employee_nif + income_type + income_locale
                    if grouping_field in grouped_lines:
                        grouped_lines[grouping_field]['current_year_income'] = self.sum_with_padding(
                            grouped_lines[grouping_field]['current_year_income'], current_year_income)
                        grouped_lines[grouping_field]['irs_retention'] = self.sum_with_padding(
                            grouped_lines[grouping_field]['irs_retention'], irs_retention)
                        grouped_lines[grouping_field]['lines'] |= line
                    else:
                        grouped_lines[grouping_field] = {
                            'employee_nif'                  : employee_nif,
                            'income_type'                   : income_type,
                            'income_locale'                 : income_locale,
                            'previous_years_income'         : previous_years_income,
                            'previous_years_income_year'    : previous_years_income_year,
                            'current_year_income'           : current_year_income,
                            'irs_retention'                 : irs_retention,
                            'required_contribution_entity_1': required_contribution_entity_1,
                            'required_contribution_entity_2': required_contribution_entity_2,
                            'required_contribution_entity_3': required_contribution_entity_3,
                            'union_quotes_line'             : union_quotes_line,
                            'overtax_retention_line'        : overtax_retention_line,
                            'category_code'                 : line.salary_rule_id.category_id.code,
                            'lines'                         : line
                        }

                    # Process taxable portion (force to income type A)
                    taxable_amount = self.taxed_value_meal_allowance_exempt_value(line.slip_id.version_id, line.slip_id)
                    # Only create line A if there is IRS retention on meal allowance
                    irs_meal_sub = line.slip_id.line_ids.filtered(lambda l: l.salary_rule_id.code == 'IRSMEALSUB')
                    if taxable_amount > 0 and irs_meal_sub and irs_meal_sub.total > 0:
                        income_type_A = "A  "  # Force to type A for taxable portion
                        current_year_income_A = str(int(taxable_amount * 100))
                        current_year_income_A = str(current_year_income_A).replace('.', '')
                        current_year_income_A = self._format_lines(current_year_income_A, 14)
                        grouping_field_A = employee_nif + income_type_A + income_locale
                        if grouping_field_A in grouped_lines:
                            grouped_lines[grouping_field_A]['current_year_income'] = self.sum_with_padding(
                                grouped_lines[grouping_field_A]['current_year_income'], current_year_income_A)
                            grouped_lines[grouping_field_A]['lines'] |= line
                        else:
                            grouped_lines[grouping_field_A] = {
                                'employee_nif'                  : employee_nif,
                                'income_type'                   : income_type_A,
                                'income_locale'                 : income_locale,
                                'previous_years_income'         : previous_years_income,
                                'previous_years_income_year'    : previous_years_income_year,
                                'current_year_income'           : current_year_income_A,
                                'irs_retention'                 : "+00000000000000",
                                'required_contribution_entity_1': required_contribution_entity_1,
                                'required_contribution_entity_2': required_contribution_entity_2,
                                'required_contribution_entity_3': required_contribution_entity_3,
                                'union_quotes_line'             : union_quotes_line,
                                'overtax_retention_line'        : overtax_retention_line,
                                'category_code'                 : line.salary_rule_id.category_id.code,
                                'lines'                         : line
                            }
                elif line.salary_rule_id.income_type and not line.salary_rule_id.exempt_income_type or line.salary_rule_id.income_type and line.salary_rule_id.category_id.code in [
                    'FAIL_ALLOW', 'COST_ALLW', 'AC_FOREIGN', 'KMS', 'PERF_BONUS', 'TERM_COMP'] or line.salary_rule_id.code == 'IRSMEALSUB':
                    employee_nif = str(line.employee_id.fiscal_number)
                    income_type = self._get_income_type_line(line)
                    income_locale = self._get_income_locale(line)
                    previous_years_income = self._get_previous_years_income(line.employee_id)
                    previous_years_income_year = self._get_previous_years_income_year(line.employee_id)
                    current_year_income = self._get_current_year_income_per_line(line)
                    irs_retention = self._get_irs_retention_per_line(line)
                    required_contribution_entity_1 = self._get_required_contribution_entity_1(line)
                    required_contribution_entity_2 = self._get_required_contribution_entity_2(line)
                    required_contribution_entity_3 = self._get_required_contribution_entity_3(line)
                    union_quotes_line = self._get_union_quotes_line(line)
                    overtax_retention_line = self._get_overtax_retention_line(line)
                    grouping_field = employee_nif + income_type + income_locale
                    if grouping_field in grouped_lines:
                        grouped_lines[grouping_field]['current_year_income'] = self.sum_with_padding(
                            grouped_lines[grouping_field]['current_year_income'], current_year_income)
                        grouped_lines[grouping_field]['irs_retention'] = self.sum_with_padding(
                            grouped_lines[grouping_field]['irs_retention'], irs_retention)
                        grouped_lines[grouping_field]['lines'] |= line
                    else:
                        grouped_lines[grouping_field] = {
                            'employee_nif'                  : employee_nif,
                            'income_type'                   : income_type,
                            'income_locale'                 : income_locale,
                            'previous_years_income'         : previous_years_income,
                            'previous_years_income_year'    : previous_years_income_year,
                            'current_year_income'           : current_year_income,
                            'irs_retention'                 : irs_retention,
                            'required_contribution_entity_1': required_contribution_entity_1,
                            'required_contribution_entity_2': required_contribution_entity_2,
                            'required_contribution_entity_3': required_contribution_entity_3,
                            'union_quotes_line'             : union_quotes_line,
                            'overtax_retention_line'        : overtax_retention_line,
                            'category_code'                 : line.salary_rule_id.category_id.code,
                            'lines'                         : line
                        }

        # NEW: Process DED lines and subtract them from income type 'A'
        # Only process DED lines that have income_type defined
        for line in self._get_payslips_lines():
            if line.salary_rule_id.category_id.code == 'DED' and line.salary_rule_id.income_type:
                # Find if there's an income type 'A' entry for this employee
                employee_nif = str(line.employee_id.fiscal_number)
                income_type = 'A  '  # Income type A formatted to 3 chars
                income_locale = self._get_income_locale(line)
                grouping_field = employee_nif + income_type + income_locale

                if grouping_field in grouped_lines:
                    # Format DED amount as negative
                    ded_amount = str(int(float_round((line.total * 100), 2)))
                    ded_amount_formatted = self._format_lines('-' + ded_amount, 14)

                    # Subtract from current year income
                    grouped_lines[grouping_field]['current_year_income'] = self.sum_with_padding(
                        grouped_lines[grouping_field]['current_year_income'],
                        ded_amount_formatted
                    )
                    # Add the DED line to the lines set
                    grouped_lines[grouping_field]['lines'] |= line

        return grouped_lines

    def convert_and_round_down(self, input_str):
        # Convert string to float, considering last two digits as decimal
        num = int(input_str) / 100

        # Round down to nearest whole number
        rounded_num = math.floor(num)

        # Convert back to string with leading zeros and two decimal places
        formatted_str = f"+{rounded_num:014.2f}".replace('.', '')
        return formatted_str

    def _get_dmr_at_3_detail(self):
        grouped_lines = self.prepare_get_dmr_at_3_detail()
        dmr_at_3_detail = ""
        index = 1
        for key, line in grouped_lines.items():
            if int(line.get('current_year_income')):
                new_line = ""
                if line.get('category_code') not in ['DED', 'GROSS', 'NET'] and line.get(
                        'income_type'):  # linhas que não são deduções exceto salario bruto, liquido e abonos para falhas
                    reg_type = "006"
                    required_contribution_line = False
                    line_number = str(index)
                    len_line_number = len(line_number)
                    zeros = ""
                    while len_line_number < 7:
                        zeros += "0"
                        len_line_number += 1
                    line_number = zeros + line_number
                    detail_line = reg_type + line_number
                    employee_nif = str(line.get('employee_nif'))
                    previous_years_income = line.get('previous_years_income')
                    previous_years_income_year = line.get('previous_years_income_year')
                    current_year_income = line.get('current_year_income')
                    irs_retention = self.convert_and_round_down(line.get('irs_retention'))
                    if line.get('lines'):
                        if irs_retention != '+0000000000000' or line.get('category_code') in ['BASIC', 'VACSUB',
                                                                                              'CHRSUB']:
                            if line.get('income_type').strip() in ['A', 'A2', 'A3', 'A4', 'A5', 'A61', 'A62', 'A63',
                                                                   'A64', 'A65',
                                                                   'A66', 'A67', 'A68']:
                                not_subject = 0
                                for slip_line in line.get('lines'):
                                    ss_rate = slip_line.slip_id.version_id.ss_regime.employee_rate
                                    if not slip_line.salary_rule_id.ss_code and slip_line.salary_rule_id.income_type and slip_line.salary_rule_id.category_id.code not in [
                                        'IRS', 'SA']:
                                        not_subject += slip_line.total
                                    income = float_round((int(current_year_income) / 100), 2) - not_subject
                                    required_contribution_line = self._get_required_contributions_per_line_new(income, ss_rate)
                            else:
                                for slip_line in line.get('lines'):
                                    ss_rate = slip_line.slip_id.version_id.ss_regime.employee_rate
                                    if (slip_line.salary_rule_id.category_id.code in ['IRS',
                                                                                      'SA'] and slip_line.total > 0) or slip_line.salary_rule_id.category_id.code in [
                                        'VACSUB', 'CHRSUB']:
                                        required_contribution_line = self._get_required_contributions_per_line_new(
                                            slip_line.amount, ss_rate)
                    income_type = line.get('income_type')
                    income_locale = line.get('income_locale')
                    required_contribution_entity_1 = line.get('required_contribution_entity_1')
                    required_contribution_entity_2 = line.get('required_contribution_entity_2')
                    required_contribution_entity_3 = line.get('required_contribution_entity_3')
                    union_quotes_line = line.get('union_quotes_line')
                    overtax_retention_line = line.get('overtax_retention_line')
                    if not required_contribution_line:
                        required_contribution_line = '+0000000000000'
                        required_contribution_entity_1 = "000000000"
                    new_line += detail_line + employee_nif + previous_years_income + previous_years_income_year + current_year_income + income_type + income_locale + irs_retention + required_contribution_line + required_contribution_entity_1 + required_contribution_entity_2 + required_contribution_entity_3 + union_quotes_line + overtax_retention_line
                    new_line = self._add_spaces_to_register(new_line)
                    dmr_at_3_detail += new_line
                    index += 1
                    self.line_count = dmr_at_3_detail.count('\n') + 1
        return dmr_at_3_detail.encode('utf-8')

    def _get_previous_years_income(self, employee):
        # se pagarem cenas de anos anteriores no periodo em que emitem esta declaração (como fazer? preciso do employee e do ano porque não vai ser para todos)
        return "+00000000000000"

    def _get_previous_years_income_year(self, employee):
        # ir buscar o ano para o employee que é recebido
        return "0000"

    def _get_current_year_income_per_line(self, line):
        total = 0
        if line.salary_rule_id.category_id.code in ['BONUS_IRS', 'BONUS_IRS_SS', 'BASIC', 'SUB', 'VACSUB', 'CHRSUB']:
            total = line.total
            total = str(int(float_round((total * 100), 2)))
            total = str(total).replace('.', '')
            return self._format_lines(total, 14)
        elif line.salary_rule_id.category_id.code == 'SA':
            # For meal allowance, calculate only the taxable amount (above exemption limit)
            total = self.taxed_value_meal_allowance_exempt_value(line.slip_id.version_id, line.slip_id)
        elif line.salary_rule_id.category_id.code == 'FAIL_ALLOW':
            wage_line = line.slip_id.line_ids.filtered(lambda x: x.category_id.code == 'BASIC')
            total = self.taxed_value_fail_allow_subject_value(wage_line[0].total, line.total)
        elif line.salary_rule_id.category_id.code == 'KMS' and line.slip_id.version_id.km_value > 0.4:
            taxed_value = line.slip_id.version_id.km_value - 0.4
            input_value = line.slip_id.input_line_ids.filtered(
                lambda l: l.input_type_id == self.env.ref('l10n_pt_hr_payroll.hr_rule_input_km')).amount
            total = taxed_value * input_value
        elif line.salary_rule_id.category_id.code == 'PERF_BONUS':
            wage = line.slip_id.version_id.wage
            total = self.perf_bonus_subject_value(wage, line.total)
        elif line.salary_rule_id.category_id.code == 'COST_ALLW':
            limit = self.env.company.default_hr_payroll_cost_allowance_exempt_limit if not line.employee_id.moe else self.env.company.default_hr_payroll_cost_allowance_moe_exempt_limit
            subject_amount = line.slip_id.version_id.cost_allw_amount - limit
            input_value = line.slip_id.input_line_ids.filtered(
                lambda l: l.input_type_id == self.env.ref('l10n_pt_hr_payroll.hr_rule_input_ac')).amount
            total = subject_amount * input_value
        elif line.salary_rule_id.category_id.code == 'AC_FOREIGN':
            limit = self.env.company.default_hr_payroll_foreign_cost_allowance_moe_exempt_limit if line.employee_id.moe else self.env.company.default_hr_payroll_foreign_cost_allowance_exempt_limit
            subject_amount = line.slip_id.version_id.cost_allw_amount - limit
            input_value = line.slip_id.input_line_ids.filtered(
                lambda l: l.input_type_id == self.env.ref('l10n_pt_hr_payroll.hr_rule_input_ac_foreign')).amount
            total = subject_amount * input_value
        elif line.category_id.code == 'TERM_COMP':
            first_contract_year = line.slip_id.employee_id._l10n_pt_get_first_contract_year() or line.slip_id.date_from.year
            antiguity = line.slip_id.date_from.year - first_contract_year
            antiguity = antiguity if antiguity > 0 else 1
            slips = line.env['hr.payslip'].search(
                [('employee_id', '=', line.slip_id.employee_id.id), ('state', 'in', ['done', 'paid'])]).filtered(
                lambda s: s.date_from >= line.slip_id.date_from + relativedelta(years=-1))
            slips -= line.slip_id
            cat_a_total = 0
            for slip in slips:
                for li in slip.line_ids.filtered(lambda l: l.salary_rule_id.category_id.code == 'BASIC'):
                    cat_a_total += li.total
            limit_value = ((cat_a_total * antiguity) / 12)
            total = limit_value if line.total > limit_value else line.total
        elif line.salary_rule_id.category_id.code != 'IRS':
            total = line.total
        if total > 0:
            total = round(total, 2)
            total = str(int(float_round((total * 100), 2)))
            total = str(total).replace('.', '')
            total = self._format_lines(total, 14)
        else:
            return "+00000000000000"
        return total

    def _get_income_subject_to_irs_dmr_at_3(self):
        total = 0
        lines = self._get_payslips_lines()
        for line in lines:
            if line.salary_rule_id.category_id.code in ['BONUS_IRS', 'BONUS_IRS_SS', 'BASIC', 'SUB', 'VACSUB',
                                                        'CHRSUB']:
                total += line.total
        if total > 0:
            total = float_round(total, 2)
            total = str(total).replace('.', '')
            total = self._format_lines(total, 14)
        else:
            return "+00000000000000"
        return total

    def _get_subject_income_line(self, line):
        return line.total

    def _get_income_type_line(self, line, income_type=False):
        type = str(income_type or line.salary_rule_id.income_type)
        while len(type) < 3:
            type += " "
        return type

    def _get_income_locale(self, line):
        locale = str(line.slip_id.income_locale)
        while len(locale) < 2:
            locale += " "
        return locale

    def _get_irs_retention_per_line(self, line):
        if line.salary_rule_id.code in ['IRSVACSUB', 'IRSCHRSUB', 'IRSMEALSUB']:
            # For allowances IRS, use the total directly
            irs_retention = line.total if line.total > 0 else 0
            irs_retention = str(int(float_round(irs_retention * 100, 0)))
            irs_retention = str(irs_retention).replace('.', '')
            irs_retention = self._format_lines(irs_retention, 14)
        elif line.salary_rule_id.category_id.code in ['IRS']:
            # For wage IRS (IRSVM), calculate with other retentions
            # Truncate the intermediate calculation (don't round up)
            other_irs = int(self._get_other_irs_retentions(line) * (line.rate / 100))
            irs_retention = line.total - other_irs
            irs_retention = irs_retention if irs_retention > 0 else 0
            irs_retention = str(int(float_round(irs_retention * 100, 0)))
            irs_retention = str(irs_retention).replace('.', '')
            irs_retention = self._format_lines(irs_retention, 14)
        elif line.salary_rule_id.category_id.code in ['BONUS_IRS', 'BONUS_IRS_SS'] and line.salary_rule_id.income_type != 'A':
            # Truncate the intermediate calculation (don't round up)
            irs_retention = int(self._get_other_irs_retentions(line) * self._get_irs_rate(line))
            irs_retention = str(int(float_round(irs_retention * 100, 0)))
            irs_retention = str(irs_retention).replace('.', '')
            irs_retention = self._format_lines(irs_retention, 14)
        else:
            irs_retention = "+00000000000000"
        return irs_retention

    def _get_other_irs_retentions(self, line):
        total = 0
        for slip_line in line.slip_id.line_ids.filtered(lambda l: l.salary_rule_id.category_id.code in ['BONUS_IRS',
                                                                                                        'BONUS_IRS_SS'] and l.salary_rule_id.income_type != 'A'):
            total += slip_line.total
        return float_round(total, 2)

    def _get_irs_rate(self, line):
        return line.slip_id.line_ids.filtered(lambda l: l.salary_rule_id.code == 'IRSVM').rate / 100

    def _get_required_contributions_per_line_new(self, amount, ss_rate):
        required_contribution = float_round(amount * (ss_rate / 100), 2)
        required_contribution = int(float_round(required_contribution * 100, 2))
        if required_contribution <= 0:
            return False
        required_contribution = str(required_contribution)
        required_contribution = self._format_lines(required_contribution, 13)
        return required_contribution

    def _get_required_contributions_per_line(self, line, ss_rate):
        if line.salary_rule_id.category_id.code in ['BONUS_SS', 'BONUS_IRS_SS', 'BASIC', 'SUB']:
            required_contribution = line.total * (ss_rate / 100)
            required_contribution = int(float_round(required_contribution * 100, 2))
            required_contribution = str(required_contribution).replace('.', '')
            required_contribution = self._format_lines(required_contribution, 13)
            return required_contribution
        else:
            return "+0000000000000"

    def _get_required_contribution_entity_1(self, line):
        entity_1 = "505305500" if line.employee_id.contrib_entity == 'ss' else "000000000"
        return entity_1

    def _get_required_contribution_entity_2(self, line):
        entity_2 = "500792968" if line.employee_id.contrib_entity == 'cga' else "000000000"
        return entity_2

    def _get_required_contribution_entity_3(self, line):
        entity_3 = "500745439" if line.employee_id.contrib_entity == 'cpas' else "000000000"
        return entity_3

    def _get_union_quotes_line(self, line):
        if line.salary_rule_id.code == 'UNION':
            union_quotes = line.total
            union_quotes = round(union_quotes, 2)
            union_quotes = str(union_quotes).replace('.', '')
            union_quotes = self._format_lines(union_quotes, 14)
            return union_quotes
        else:
            return "+0000000000000"

    def _get_overtax_retention_line(self, line):
        # n sei o que é isto ainda
        return "+0000000000000"

    # ----------------------- DMR-AT Trailer----------------------

    def _get_dmr_at_trailer(self):
        reg_type = "009"
        total_previous_income = self._get_total_previous_income()
        total_income = self._get_total_income_009()
        total_irs_retention = self._get_total_irs_retention_009()
        total_required_contribution = self._get_total_required_contributions_009()
        total_union_quotes = self._get_total_union_quotes_009()
        total_overtax_retention = self._get_total_overtax_retention_009()
        lines_count = self._get_line_count_trailer_dmr_at_009()
        dmr_at_trailer = reg_type + total_previous_income + total_income + total_irs_retention + total_required_contribution + total_union_quotes + total_overtax_retention + lines_count
        dmr_at_trailer = self._add_spaces_to_register(dmr_at_trailer)
        return dmr_at_trailer.encode('utf-8')

    def _get_total_previous_income(self):
        total = 0
        lines = self._get_payslips_lines()
        employees = []
        for line in lines:
            employees.append(line.employee_id)
            employees = list(set(employees))
        for emp in employees:
            total += float(self._get_previous_years_income(emp))
        total = round(total, 2)
        if total > 0:
            total = str(total).replace('.', '')
            total = self._format_lines(total, 15)
        else:
            return "+000000000000000"
        return total

    def _get_total_income_009(self):
        total = 0
        lines = self._get_payslips_lines()
        for line in lines:
            total += float(self._get_current_year_income_per_line(line))
        total = round(total, 2)
        if total > 0:
            total = str(total).replace('.', '')
            total = self._format_lines(total, 16)
        else:
            return "+0000000000000000"
        return total

    def _get_total_irs_retention_009(self):
        total = 0
        lines = self._get_payslips_lines()
        for line in lines:
            total += float(self._get_irs_retention_per_line(line))
        total = round(total, 2)
        if total > 0:
            total = str(total).replace('.', '')
            total = self._format_lines(total, 15)
        else:
            return "+000000000000000"
        return total

    def _get_total_required_contributions_009(self):
        total = 0
        lines = self._get_payslips_lines()
        for line in lines:
            ss_rate = line.slip_id.version_id.ss_regime.employee_rate
            total += float_round(float(self._get_required_contributions_per_line(line, ss_rate)), 2)
        total = float_round(total, 2)
        if total > 0:
            total = str(total).replace('.', '')
            total = self._format_lines(total, 15)
        else:
            return "+000000000000000"
        return total

    def _get_total_union_quotes_009(self):
        total = 0
        lines = self._get_payslips_lines()
        for line in lines:
            total += float(self._get_union_quotes_line(line))
        total = round(total, 2)
        if total > 0:
            total = str(total).replace('.', '')
            total = self._format_lines(total, 15)
        else:
            return "+000000000000000"
        return total

    def _get_total_overtax_retention_009(self):
        total = 0
        lines = self._get_payslips_lines()
        for line in lines:
            total += float(self._get_overtax_retention_line(line))
        total = float_round(total, 2)
        if total > 0:
            total = str(total).replace('.', '')
            total = self._format_lines(total, 15)
        else:
            return "+000000000000000"
        return total

    def _get_line_count_trailer_dmr_at_009(self):
        line_count = self.line_count + 1
        line_count = str(line_count)
        len_line_count = len(line_count)
        zeros = ""
        while len_line_count < 7:
            zeros += "0"
            len_line_count += 1
        line_count = zeros + line_count
        return line_count

    def _get_line_count_trailer_dmr_at(self):
        line_count = self.line_count + 2  # +2 pq é o registo 004 e 005
        line_count = str(line_count)
        len_line_count = len(line_count)
        zeros = ""
        while len_line_count < 7:
            zeros += "0"
            len_line_count += 1
        line_count = zeros + line_count
        return line_count

    # ----------------------DECLARATION TRAILER--------------------

    def _get_declaration_trailer(self):
        reg_type = "099"
        lines_count = self._get_lines_for_declaration_trailer()
        declaration_trailer = reg_type + lines_count
        declaration_trailer = self._add_spaces_to_register(declaration_trailer)
        return declaration_trailer.encode('utf-8')

    def _get_lines_for_declaration_trailer(self):
        lines = int(self._get_line_count_trailer_dmr_at()) + 1
        lines = str(lines)
        zeros = ""
        len_lines = len(lines)
        while len_lines < 9:
            zeros += "0"
            len_lines += 1
        lines = zeros + lines
        return lines

    def _get_file_trailer(self):
        reg_type = "999"
        lines_count = self._get_lines_for_file_trailer()
        file_trailer = reg_type + lines_count
        file_trailer = self._add_spaces_to_register(file_trailer)
        return file_trailer.encode('utf-8')

    def _get_lines_for_file_trailer(self):
        lines = int(self._get_lines_for_declaration_trailer()) + 2
        lines = str(lines)
        zeros = ""
        len_lines = len(lines)
        while len_lines < 9:
            zeros += "0"
            len_lines += 1
        lines = zeros + lines
        return lines

    def validate_fields(self):
        if not self.env.company.vat:
            raise ValidationError(_('The current company has no VAT.'))
        if not self.env.company.finance_service_code:
            raise ValidationError(_('The current company has no Finance Service Code'))
        if not self.env.company.legal_rep_nif:
            raise ValidationError(_('The current company has no Legal Representant VAT'))
        if not self.env.company.accountant_nif:
            raise ValidationError(_('The current company has no Certified Accountant VAT'))
        if not self._get_payslips_lines():
            raise ValidationError(_('There are no done payslips in the time period selected'))

    def execute(self):
        self.validate_fields()
        file_header = self._get_file_header()
        dec_header = self._get_declaration_header()
        dmr_header = self._get_dmr_header()
        dmr_at_1_detail = self._get_dmr_at_1_detail()
        dmr_at_2_detail = self._get_dmr_at_2_detail()
        dmr_at_3_detail = self._get_dmr_at_3_detail()
        dmr_at_trailer = self._get_dmr_at_trailer()
        declaration_trailer = self._get_declaration_trailer()
        file_trailer = self._get_file_trailer()
        file_content = base64.b64encode(
            file_header + dec_header + dmr_header + dmr_at_1_detail + dmr_at_2_detail + dmr_at_3_detail + dmr_at_trailer + declaration_trailer + file_trailer)
        a = self.env['ir.attachment'].create({
            'name'    : 'DMR_' + str(self.date_end.strftime('%Y%m')) + '.txt',
            'datas'   : file_content,
            'mimetype': 'application/text',
        })

        return {
            "type": "ir.actions.act_url",
            "url" : f"/web/content/{a.id}",
        }
