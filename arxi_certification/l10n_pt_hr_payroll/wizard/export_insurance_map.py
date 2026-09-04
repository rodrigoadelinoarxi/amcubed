import base64
import unicodedata
from datetime import timedelta
import calendar
from dateutil.relativedelta import relativedelta
from datetime import date, datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

from odoo.tools import float_round

_logger = logging.getLogger(__name__)

ENTRIES_WORK = ['WORK100', 'VACATION']


class ExportInsuranceMap(models.TransientModel):
    _name = 'export.insurance.map.wizard'
    _description = 'Wizard to export Insurance Map File'

    date_start = fields.Date(
        string='Start Date',
        default=fields.Date.today().replace(month=fields.Date.today().month, day=1) - relativedelta(months=1))
    date_end = fields.Date(
        string='End Date',
        default=fields.Date.today().replace(day=1) - relativedelta(days=1))

    policy_number = fields.Char(default=lambda self: self.env.company.insurance_policy_number)

    line_format = fields.Selection([
        ('LF', 'Unix (LF)'),
        ('CRLF', 'Windows (CRLF)'),
    ], default='LF')

    @api.onchange('date_start')
    def onchange_date_start(self):
        """
        When changing the start date, automatically put the end date at the end of the month.
        :return:
        """
        if self.date_start:
            self.date_end = self.date_start + relativedelta(months=1, days=-1)

    def _add_spaces_to_register(self, register):
        while len(register) < 124:
            register += " "
        register += "\n"
        return register

    def _add_spaces_to_line(self, line, length):
        while len(line) < length:
            line += " "
        return line

    def _get_payslips_lines(self, regime):
        lines = []
        payslips = self.env['hr.payslip'].search([('date_to', '<=', self.date_end), ('state', 'in', ['done', 'paid']),
                                                  ('version_id.ss_regime', '=', regime),
                                                  ('employee_id.policy_number', '=', self.policy_number)]).filtered(
            lambda slip: slip.date_to.year == self.date_end.year)
        for payslip in payslips:
            if payslip.date_to.month != self.date_start.month:
                continue
            for line in payslip.line_ids:
                if not line.employee_id.ssnid:
                    raise ValidationError(_(f'An employee has no Social Security Number: %s', line.employee_id.name))
                if not line.employee_id.birthday:
                    raise ValidationError(_(f'An employee has no birthday: %s', line.employee_id.name))
                if not line.employee_id.contrib_entity:
                    raise ValidationError(
                        _('An employee has no Contribution Entity selected: %s', line.employee_id.name))
                if line.employee_id.contrib_entity == 'ss':
                    lines.append(line)
        return lines

    def _format_lines(self, line, length):
        zeros = ""
        len_line = len(line)
        while len_line < length:
            zeros += "0"
            len_line += 1
        line = zeros + line
        return line

    # --------------------------------R0 REGISTER------------------
    def _get_r0_register(self):
        tip_reg = "R0"
        model = "FOLHAF"
        spaces = "  "
        version = "01"
        date = str(self.date_end.strftime('%Y%m'))
        policy_number = self.get_policy_number()
        insurance_company_code = self.env.company.insurance_company.code if self.env.company.insurance_company else ''
        r0_register = tip_reg + model + spaces + version + date + policy_number + insurance_company_code
        r0_register = self._add_spaces_to_register(r0_register)
        return r0_register.encode('utf-8')

    # ----------------------------R1 REGISTER---------------------
    def _get_r1_register(self):
        tip_reg = "R1"
        niss_company = self._get_company_niss()
        company_establishment = "0001"
        nif_company = self._get_company_nif()
        company_name = self._get_company_name()
        ref_date = str(self.date_end.strftime('%Y%m'))
        policy_number = self.get_policy_number()
        insurance_company_code = self.env.company.insurance_company.code if self.env.company.insurance_company else ''
        r1_register = tip_reg + niss_company + company_establishment + nif_company + company_name
        while len(r1_register) < 92:
            r1_register += " "

        r1_register += ref_date + policy_number + insurance_company_code
        r1_register = self._add_spaces_to_register(r1_register)
        return r1_register.encode('utf-8')

    def _get_company_niss(self):
        return str(self.env.company.niss)

    def _get_company_nif(self):
        nif = self.env.company.vat
        if 'PT' in nif:
            nif = nif[2:]
        return nif

    def _get_company_name(self):
        name = self.env.company.name
        normalized_string = unicodedata.normalize('NFD', name)
        output_string = ''.join(char for char in normalized_string if unicodedata.category(char) != 'Mn')
        output_string = self._add_spaces_to_line(output_string, 60)
        return output_string

    # -------------------------R2 REGISTER---------------------

    def sum_with_padding(self, val1, val2):
        standard_size = len(val1.replace('+', ''))
        clean_val1 = int(val1.replace('+', '').replace('-', ''))
        if '-' in val1:
            clean_val1 = clean_val1 * -1
        clean_val2 = int(val2.replace('+', '').replace('-', ''))
        if '-' in val2:
            clean_val2 = clean_val2 * -1
        sum = clean_val1 + clean_val2
        sum_string = str(abs(sum))
        if sum < 0:
            sum_string = self._format_lines(sum_string, 9)
            sum_string += '-'
        return self._format_lines(sum_string, standard_size)

    # We need to group by insurance_code because we can't have two lines with the same code per employee
    def group_lines(self, regime):
        grouped_lines = {}

        for payslip in self.env['hr.payslip'].search(
                [('date_to', '<=', self.date_end), ('state', 'in', ['done', 'paid']),
                 ('version_id.ss_regime', '=', regime)]).filtered(
            lambda slip: slip.date_to.year == self.date_end.year and slip.date_to.month == self.date_start.month):

            company_niss = self._get_company_niss()
            company_establishment = "0001"
            employee = payslip.employee_id
            employee_niss = self._get_employee_niss(employee)
            employee_name = self._get_employee_name(employee)
            employee_birth_date = self._get_employee_birth_date(employee)

            corrections = payslip.worked_days_line_ids.filtered(lambda w: w.is_correction)
            for line_corrected in corrections:
                line = payslip.line_ids.filtered(lambda l: l.salary_rule_id.insurance_code)[0] if payslip.line_ids.filtered(
                    lambda l: l.salary_rule_id.insurance_code) else None
                if not line:
                    continue
                insurance_code = line.salary_rule_id.insurance_code
                worked_days = self._get_worked_days_per_line(line, line_corrected)
                income_type = f" {insurance_code}"
                income = self._get_income_per_line(line, line_corrected)
                income_date = self._get_correction_date(line_corrected)

                if income == "000000000-":
                    continue

                key = f"{employee_niss}_{insurance_code}_NEG"
                grouped_lines[key] = {
                    'tip_reg'              : "R2",
                    'niss_company'         : company_niss,
                    'company_establishment': company_establishment,
                    'employee_niss'        : employee_niss,
                    'employee_name'        : employee_name,
                    'employee_birth_date'  : employee_birth_date,
                    'income_date'          : income_date,
                    'worked_days'          : worked_days,
                    'income_type'          : income_type,
                    'income'               : income,
                    'slip_id'              : payslip,
                    'salary_rule_id'       : line.salary_rule_id,
                    'lines'                : line
                }

            for line in payslip.line_ids:
                if not line.salary_rule_id.insurance_code and not line.salary_rule_id.in_insurance_map:
                    continue
                if not line.employee_id.ssnid or not line.employee_id.birthday or not line.employee_id.contrib_entity:
                    raise ValidationError(_('Missing required employee info: %s', line.employee_id.name))
                if line.employee_id.contrib_entity != 'ss':
                    continue

                if line.total <= 0:
                    continue

                insurance_code = line.salary_rule_id.insurance_code
                worked_days = self._get_worked_days_per_line(line, False)
                income_type = f" {insurance_code}"
                income = self._get_income_per_line(line, False)
                income_date = str(self.date_end.strftime('%Y%m'))

                key = f"{employee_niss}_{insurance_code}_POS"
                if key in grouped_lines:
                    grouped_lines[key]['income'] = self.sum_with_padding(grouped_lines[key]['income'], income)
                    grouped_lines[key]['lines'] |= line
                else:
                    grouped_lines[key] = {
                        'tip_reg'              : "R2",
                        'niss_company'         : company_niss,
                        'company_establishment': company_establishment,
                        'employee_niss'        : employee_niss,
                        'employee_name'        : employee_name,
                        'employee_birth_date'  : employee_birth_date,
                        'income_date'          : income_date,
                        'worked_days'          : worked_days,
                        'income_type'          : income_type,
                        'income'               : income,
                        'slip_id'              : payslip,
                        'salary_rule_id'       : line.salary_rule_id,
                        'lines'                : line
                    }

        return grouped_lines

    def _get_r2_register(self, regime):
        r2_register = ""
        for key, line in self.group_lines(regime).items():
            if line['salary_rule_id'].in_insurance_map and line['salary_rule_id'].insurance_code:
                tip_reg = "R2"
                niss_company = line['niss_company']
                company_establishment = "0001"
                employee_niss = line['employee_niss']
                employee_name = line['employee_name']
                employee_birth_date = line['employee_birth_date']
                income_date = line['income_date']
                worked_days = line['worked_days']
                income_type = line['income_type']
                income = line['income']
                if '000000000' not in income:
                    r2_line = tip_reg + niss_company + company_establishment + employee_niss + employee_name + employee_birth_date + income_date + worked_days + income_type + income
                    r2_line = self._add_spaces_to_register(r2_line)
                    r2_register += r2_line
        return r2_register.encode('utf-8')

    def _get_employee_niss(self, employee):
        return str(employee.ssnid)

    def _get_employee_name(self, employee):
        name = employee.name
        normalized_string = unicodedata.normalize('NFD', name)
        output_string = ''.join(char for char in normalized_string if unicodedata.category(char) != 'Mn')
        output_string = self._add_spaces_to_line(output_string, 60)
        return output_string

    def _get_employee_birth_date(self, employee):
        birth_date = employee.birthday.strftime('%Y%m%d')
        return birth_date

    def _get_corrections(self, line):
        lines_corrected = line.slip_id.worked_days_line_ids.filtered(
            lambda w: w.is_correction and w.ref_date and w.ref_date.split('.')[1] == line.slip_id.date_from.month)
        if lines_corrected:
            return True
        return False

    def _get_worked_days_part_time(self, line):
        if line.salary_rule_id.insurance_code == 'P' and line.salary_rule_id.in_insurance_map:
            worked_hours = 0
            worked_entries = line.slip_id.worked_days_line_ids.filtered(
                lambda w: w.work_entry_type_id.code in ENTRIES_WORK and not w.is_correction)
            for entry in worked_entries:
                worked_hours += entry.number_of_hours
            worked_days = int(worked_hours / 6)
            surplus = worked_hours % 6
            hours_not_considered = 0
            days_not_considered = 0
            if surplus > 3:
                worked_days += 1
            elif surplus <= 3:
                worked_days += 0.5
            lines_to_discount = line.slip_id.worked_days_line_ids.filtered(
                lambda w: w.work_entry_type_id.discounts_salary and not w.is_correction and w.ref_date and
                          w.ref_date.split('.')[1] == line.slip_id.date_from.month)
            for line in lines_to_discount:
                hours_not_considered += line.number_of_hours
                days_not_considered = int(hours_not_considered / 6)
                surplus = days_not_considered % 6
                if surplus > 3:
                    days_not_considered += 1
                elif surplus <= 3:
                    days_not_considered += 0.5
            worked_days = worked_days if worked_days <= 30 else 30
            worked_days = worked_days - days_not_considered
            worked_days = "0" + str(worked_days) if worked_days < 10 else str(
                worked_days)
            worked_days = str(worked_days)
            worked_days = worked_days.replace('.', '')
            if len(worked_days) < 2:
                worked_days = '0' + worked_days
            while len(worked_days) < 3:
                worked_days += '0'
            if line.total > 0:
                worked_days += '0'
            else:
                worked_days += '-'
            return worked_days
        else:
            return '0000'

    def _get_worked_days_corrected(self, line_corrected, insurance_code):
        return '000-' if insurance_code != 'P' else (str(line_corrected.number_of_days).replace('.', '') + '-').zfill(4)

    def _get_worked_days_per_line(self, line, line_corrected):
        if line.salary_rule_id.insurance_code != 'P' and line.salary_rule_id.in_insurance_map:
            if line.salary_rule_id.insurance_code == '2':
                worked_days = line.quantity if line.quantity <= 30 else 30
                worked_days = "0" + str(worked_days).replace('.', '') if worked_days < 10 else str(worked_days).replace(
                    '.', '')
                while len(worked_days) < 3:
                    worked_days += '0'
                if line.total > 0:
                    worked_days += '0'
                else:
                    worked_days += '-'
                return worked_days
            return '0000' if not line_corrected else '000-'
        if line.slip_id.version_id.time_credit:
            worked_days = self._get_worked_days_part_time(line)
            return worked_days
        if line.salary_rule_id.insurance_code == 'P' and line.salary_rule_id.in_insurance_map:
            worked_days = str(line.slip_id.days_worked)
            worked_days = worked_days.replace('.', '')
            if line_corrected:
                worked_days = self._get_worked_days_corrected(line_corrected, 'P')
            while len(worked_days) < 4:
                worked_days += '0'
            return worked_days

    def _get_income_type(self, line):
        type = str(line.salary_rule_id.insurance_code)
        type = " " + type
        return type

    def _get_income_per_corrected_line(self, line, line_corrected):
        if line.salary_rule_id.insurance_code == 'P' and line.salary_rule_id.in_insurance_map:
            income = (line.slip_id.version_id.wage / 30) * line_corrected.number_of_days
        elif line.salary_rule_id.insurance_code == 'R' and line.salary_rule_id.in_insurance_map:
            income = line.slip_id.version_id.foodValue * line_corrected.number_of_days
        else:
            income = (line.total / 30) * line_corrected.number_of_days
        income = float_round(income, 2)
        income = f"{income:.2f}"
        income = income.replace('.', '')
        income = self._format_lines(income, 9)
        income += '-'
        return income

    def taxed_value_fail_allow_exempt_value(self, wage):
        exempt_value = ((wage * 14) / 12) * 0.05
        return float_round(exempt_value, 2)

    def _get_total_income_line(self, regime):
        total = 0
        for line in self._get_payslips_lines(regime):
            if line.salary_rule_id.insurance_code and line.salary_rule_id.in_insurance_map:
                total += line.total
                if line.salary_rule_id.code == 'FAIL_ALLOW':
                    wage_line = line.slip_id.line_ids.filtered(lambda x: x.salary_rule_id.code == 'BASIC')
                    fail_allow_amount_exempt = self.taxed_value_fail_allow_exempt_value(wage_line.total)
                    if fail_allow_amount_exempt > 0 and line.total > fail_allow_amount_exempt:
                        total -= fail_allow_amount_exempt
                    else:
                        total -= line.total
                elif line.category_id.code == 'COST_ALLW':
                    exempt_value = self.env.company.default_hr_payroll_cost_allowance_exempt_limit if not line.employee_id.moe else self.env.company.default_hr_payroll_cost_allowance_moe_exempt_limit
                    exempt_value = line.slip_id.version_id.cost_allw_amount if line.slip_id.version_id.cost_allw_amount <= exempt_value else exempt_value
                    if line.amount <= exempt_value:
                        total -= line.total
                    else:
                        total -= float_round(exempt_value * line.quantity, 2)
        total = float_round(total, 2) - self.get_total_corrections(regime)
        total = float_round(total, 2)
        return total

    def _get_total_contributions(self, regime):
        total = float(self._get_total_income_line(regime))
        total = total * self._get_rate(regime)
        total = float_round(total, 2)
        total = f"{total:.2f}"
        total = str(total).replace('.', '')
        total = self._format_lines(str(total), 12)
        return total + "0"

    def taxed_value_fail_allow_subject_value(self, wage, amount):
        taxed_amount = 0
        exempt_value = ((wage * 14) / 12) * 0.05
        taxed_amount += amount - exempt_value
        return round(taxed_amount, 2) if taxed_amount > 0 else 0

    def taxed_value_fail_allow_exempt_value(self, wage):
        exempt_value = ((wage * 14) / 12) * 0.05
        return round(exempt_value, 2)

    def _get_income_per_line(self, line, line_corrected):
        negative = False
        if line.salary_rule_id.code == 'FAIL_ALLOW':
            wage_line = line.slip_id.line_ids.filtered(lambda x: x.salary_rule_id.code == 'BASIC')
            income = self.taxed_value_fail_allow_subject_value(wage_line.total, line.total)
            income = f"{income:.2f}"
            income = str(income)
            income = income.replace('.', '')
            income = self._format_lines(income, 9)
            income += "0" if not line_corrected else "-"
            return income
        if line.category_id.code == 'COST_ALLW':
            income = line.total
            exempt_value = self.env.company.default_hr_payroll_cost_allowance_exempt_limit if not line.employee_id.moe else self.env.company.default_hr_payroll_cost_allowance_moe_exempt_limit
            exempt_value = line.slip_id.version_id.cost_allw_amount if line.slip_id.version_id.cost_allw_amount <= exempt_value else exempt_value
            if line.amount <= exempt_value:
                income -= line.total
            else:
                income -= exempt_value * line.quantity
            income = f"{income:.2f}"
            income = str(income)
            income = income.replace('.', '')
            income = self._format_lines(income, 9)
            income += "0" if not line_corrected else "-"
            return income
        if line_corrected:
            income = self._get_income_per_corrected_line(line, line_corrected)
            return income
        income = f"{line.total:.2f}"
        income = str(income)
        income = income.replace('.', '')
        if '-' in income:
            income = income.replace('-', '')
            negative = True
        income = self._format_lines(income, 9)
        income += "0" if not line_corrected and not negative else "-"
        return income

    def _get_income_per_line_exempt(self, line, line_corrected):
        wage_line = line.slip_id.line_ids.filtered(lambda x: x.salary_rule_id.code == 'BASIC')
        income = self.taxed_value_fail_allow_exempt_value(wage_line.total)
        income = f"{income:.2f}"
        income = str(income)
        income = income.replace('.', '')
        income = self._format_lines(income, 9)
        income += "0" if not line_corrected else "-"
        return income
        if line_corrected:
            income = self._get_income_per_corrected_line(line, line_corrected)
            return income
        income = f"{line.total:.2f}"
        income = str(income)
        income = income.replace('.', '')
        income = self._format_lines(income, 9)
        income += "0" if not line_corrected else "-"
        return income

    def _get_correction_date(self, line_corrected):
        date = line_corrected.ref_date.replace('.', '')
        return date

    # -----------------------R3 REGISTER---------------------

    def _get_r3_register(self, regime, total_r2_reg):
        tip_reg = "R3"
        company_niss = self._get_company_niss()
        company_establishment = "0001"  # confirmar
        nines = "99999999999"
        total_income = self._get_total_income(regime)
        total_contributions = self._get_total_contributions(regime)
        contrib_rate = self._get_contrib_rate(regime)
        # total_r2_reg = self._get_r2_count(regime)
        total_r2_reg = self._format_lines(str(total_r2_reg), 6)
        r3_register = tip_reg + company_niss + company_establishment + nines + total_income + total_contributions + contrib_rate + total_r2_reg
        r3_register = self._add_spaces_to_register(r3_register)
        return r3_register.encode('utf-8')

    def get_total_corrections(self, regime):
        income = 0
        payslips = self.env['hr.payslip'].search([
            ('date_to', '<=', self.date_end),
            ('state', 'in', ['done', 'paid']),
            ('version_id.ss_regime', '=', regime),
        ]).filtered(
            lambda slip: slip.date_to.year == self.date_end.year and slip.date_to.month == self.date_start.month)

        for payslip in payslips:
            corrections = payslip.worked_days_line_ids.filtered(lambda w: w.is_correction)
            for line_corrected in corrections:
                valid_lines = payslip.line_ids.filtered(
                    lambda l: l.salary_rule_id.insurance_code in ['P', 'R', 'F',
                                                                  'N'] and l.salary_rule_id.in_insurance_map
                )
                if not valid_lines:
                    continue
                line = valid_lines[0]
                code = line.salary_rule_id.insurance_code

                if code == 'P':
                    income += float_round(payslip.version_id.wage / 30 * line_corrected.number_of_days, 2)
                elif code == 'R':
                    income += float_round(payslip.version_id.foodValue * line_corrected.number_of_days, 2)
                else:
                    income += float_round((line.total / 30) * line_corrected.number_of_days, 2)

        return float_round(income, 2)

    def _get_total_income(self, regime):
        total = 0
        for line in self._get_payslips_lines(regime):
            if line.salary_rule_id.insurance_code and line.salary_rule_id.in_insurance_map:
                total += line.total
                if line.salary_rule_id.code == 'FAIL_ALLOW':
                    wage_line = line.slip_id.line_ids.filtered(lambda x: x.salary_rule_id.code == 'BASIC')
                    fail_allow_amount_exempt = self.taxed_value_fail_allow_exempt_value(wage_line.total)
                    if fail_allow_amount_exempt > 0 and line.total > fail_allow_amount_exempt:
                        total -= fail_allow_amount_exempt
                    else:
                        total -= line.total
                if line.category_id.code == 'COST_ALLW':
                    exempt_value = self.env.company.default_hr_payroll_cost_allowance_exempt_limit if not line.employee_id.moe else self.env.company.default_hr_payroll_cost_allowance_moe_exempt_limit
                    exempt_value = line.slip_id.version_id.cost_allw_amount if line.slip_id.version_id.cost_allw_amount <= exempt_value else exempt_value
                    if line.amount <= exempt_value:
                        total -= line.total
                    else:
                        total -= exempt_value * line.quantity
        total = float_round(total, 2) - self.get_total_corrections(regime)
        total = float_round(total, 2)
        total = f"{total:.2f}"
        total = str(total).replace('.', '')
        total = self._format_lines(str(total), 14)
        return total + "0"

    def _get_rate(self, ssregime):
        regime = self.env['ss.regime'].browse(ssregime)
        return (regime.employer_rate + regime.employee_rate) / 100

    def _get_contrib_rate(self, ssregime):
        regime = self.env['ss.regime'].browse(ssregime)
        rate = float_round(regime.employer_rate + regime.employee_rate, 2)
        rate = f"{rate:.2f}"
        rate = str(rate).replace('.', '')
        while len(rate) < 4:
            rate += "0"
        return rate

    def _get_r2_count(self, regime):
        count = 0
        for line in self._get_payslips_lines(regime):
            if line.salary_rule_id.insurance_code and line.total > 0 and line.salary_rule_id.in_insurance_map:
                count += 1
            if line.salary_rule_id.insurance_code in ['P', 'R', 'F', 'N'] and line.salary_rule_id.in_insurance_map:
                lines_corrected = line.slip_id.worked_days_line_ids.filtered(
                    lambda w: w.is_correction and w.ref_date and w.ref_date.split('.')[
                        1] == line.slip_id.date_from.month)
                for line_corrected in lines_corrected:
                    if self._get_income_per_line(line, line_corrected) != '000000000-':
                        count += 1
        count = self._format_lines(str(count), 6)
        return count

    def validate_fields(self):
        if not self.env.company.niss:
            raise ValidationError(_('The current company has no NISS.'))
        if not self.env.company.company_type:
            raise ValidationError(_('The current company has no company type.'))
        if not self.env.company.insurance_policy_number:
            raise ValidationError(_('The current company has no Insurance Policy Number.'))
        if not self.env.company.insurance_company:
            raise ValidationError(_('The current company has no Insurance Company selected.'))
        if not self._get_payslips_lines(self.get_ss_regimes()):
            raise ValidationError(_('There are no done payslips in the time period selected'))

    def get_ss_regimes(self):
        ssRegimes = []
        contracts = []
        payslips = self.env['hr.payslip'].search([('date_to', '<=', self.date_end), ('state', 'in', ['done', 'paid']),
                                                  ('employee_id.policy_number', '=', self.policy_number)])
        slips = payslips.filtered(
            lambda s: s.date_to.month == self.date_start.month and s.date_to.year == self.date_end.year)
        for slip in slips:
            contracts.append(slip.version_id)
        for contract in contracts:
            ssRegimes.append(contract.ss_regime.id)
        ssRegimes = list(set(ssRegimes))
        return ssRegimes

    def get_policy_number(self):
        policy_number = self.policy_number
        policy_number = self._format_lines(policy_number, 20)
        return policy_number

    def execute(self):
        self.validate_fields()
        file_content = b''
        r0_register = self._get_r0_register()
        regimes = self.get_ss_regimes()
        for regime in regimes:
            r1_register = self._get_r1_register()
            r2_register = self._get_r2_register(regime)

            decoded_r2_register = r2_register.decode('utf-8')
            r2_register_lines = decoded_r2_register.split('\n')
            total_r2_reg = 0
            for r in r2_register_lines:
                if r:
                    total_r2_reg += 1

            r3_register = self._get_r3_register(regime, total_r2_reg)
            file_content += r1_register + r2_register + r3_register

        if self.line_format == 'CRLF':
            file_content = file_content.decode('utf-8')
            file_content = file_content.replace('\n', '\r\n')
            r0_register = r0_register.decode('utf-8').replace('\n', '\r\n')
            file_content = base64.b64encode((r0_register + file_content).encode('utf-8')).decode('utf-8')
        else:
            file_content = base64.b64encode(r0_register + file_content).decode('utf-8')

        insurance_code = self.env.company.insurance_company.code if self.env.company.insurance_company else ''
        a = self.env['ir.attachment'].create({
            'name'    : str(insurance_code) + self.get_policy_number() + str(
                self.date_end.strftime('%Y%m')) + '.EUR',
            'datas'   : file_content,
            'mimetype': 'application/text',
        })

        return {
            "type": "ir.actions.act_url",
            "url" : f"/web/content/{a.id}",
        }
