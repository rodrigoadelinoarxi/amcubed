from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _l10n_pt_get_first_contract_year(self):
        """Ano do primeiro contrato do colaborador.

        v19: hr.contract foi fundido em hr.version. contract_ids[0] passou a
        version_ids[0], mas as versoes sem contrato tem date_start a False,
        por isso e preciso filtrar antes de calcular o minimo.
        """
        self.ensure_one()
        dates = [v.date_start for v in self.version_ids if v.date_start]
        return min(dates).year if dates else False

    is_pt_company = fields.Boolean(compute='_compute_is_pt_company', store=False)
    depending = fields.Integer(string=u'Number of Holders', required=False,
                               help=u"Number of Holders, that is, members of the couple who are employed.", default=1,
                               tracking=True)
    fiscal_number = fields.Char(string=u'Fiscal Number', required=False,
                                help=u"Fiscal Number.", tracking=True)
    handycap = fields.Boolean(string=u'Handicapped', required=False,
                              help=u"If the employee has an officially recognized disability.")
    spouse_handycap = fields.Boolean(string=u'Spouse Handicapped', tracking=True)

    dependent_handycap = fields.Integer(string=u'Dependents Handicapped(Number)', default=0, tracking=True)

    irs_monthly_tax = fields.Float(string=u'The Declarant opts for the monthly retention tax of: ', tracking=True)
    irs_monthly_tax_chr = fields.Float(string=u'The Declarant opts for the monthly retention tax of (Christmas): ',
                                       tracking=True)
    irs_monthly_tax_vac = fields.Float(string=u'The Declarant opts for the monthly retention tax of (Vacation): ',
                                       tracking=True)

    insurance_company = fields.Many2one('hr.insurance.company', string="Insurance Company", required=False,
                                        default=lambda self: self.env.company.insurance_company,
                                        help=u"Insurance Company.", tracking=True)
    insurance_company_name = fields.Char(string="Insurance Company Name (Legacy)",
                                         help="Legacy field - stores the old insurance company name before migration",
                                         tracking=True)

    union_worker = fields.Boolean(string="Union", default=False, tracking=True)

    contrib_entity = fields.Selection([
        ('ss', 'Social Security'),
        ('cga', 'CGA'),
        ('cpas', 'CPAS'),
    ], default='ss', tracking=True)

    policy_number = fields.Char(string=u'Policy Number', required=False,
                                default=lambda self: self.env.company.insurance_policy_number,
                                help=u"Work accident policy number.", tracking=True)

    cc_expiration_date = fields.Date(tracking=True)

    moe = fields.Boolean(string="MOE/TL", default=False, tracking=True)

    work_accident_coefficient = fields.Float(string="Work Accident Coefficient",
                                             default=lambda self: self.env.company.work_accident_coefficient,
                                             tracking=True)

    income_year = fields.Char(string="Income Year", default=lambda self: fields.Datetime.now().year, tracking=True)

    total_income = fields.Float(string="Total Annual Income", compute='_get_annual_report_values', store=True,
                                readonly=False)
    irs_deducted_value = fields.Float(string="IRS Deducted Value", compute='_get_annual_report_values', store=True,
                                      readonly=False)
    ss_deducted_value = fields.Float(string="SS Deducted Value", compute='_get_annual_report_values', store=True,
                                     readonly=False)
    union_deducted_value = fields.Float(string="Union Deducted Value", compute='_get_annual_report_values', store=True,
                                        readonly=False)
    annual_income_report_date = fields.Date(string="Report Date", default=fields.Datetime.now(), store=True)

    pensioner = fields.Boolean(string="Pensioner", default=False, tracking=True)

    @api.depends('company_id', 'company_id.country_id')
    def _compute_is_pt_company(self):
        for rec in self:
            rec.is_pt_company = rec.company_id.country_id.code == 'PT' if rec.company_id and rec.company_id.country_id else False

    def write(self, vals):
        if 'irs_monthly_tax' in vals:
            if vals['irs_monthly_tax'] * 100 < 0 or vals['irs_monthly_tax'] * 100 > 100:
                raise ValidationError(_('Rate should be between 0 and 100'))
        if 'ssnid' in vals:
            if not vals['ssnid'].isdigit():
                raise ValidationError(_('SSN should have numbers only!'))
            if len(vals['ssnid']) != 11:
                raise ValidationError(_('SSN should have 11 digits!'))
        return super(HrEmployee, self).write(vals)

    @api.onchange('income_year')
    def _check_income_year(self):
        if self.income_year and not self.income_year.isdigit():
            raise ValidationError(_('Income year should have numbers only!'))
        if self.income_year and int(self.income_year) > fields.Datetime.now().year:
            raise ValidationError(_('Income year cannot be greater than current year'))

    @api.depends('income_year')
    def _get_annual_report_values(self):
        for rec in self:
            if not rec.id or not isinstance(rec.id, int):
                # Avoid computing on in-memory or unsaved records
                return

            rec.total_income = rec._get_total_irs_subject_income() + rec._get_total_exempt_income()
            rec.irs_deducted_value = rec._get_total_irs_retention()
            rec.ss_deducted_value = rec._get_total_ss_retention()
            rec.union_deducted_value = rec._get_total_union_contribution()


    def _get_total_irs_subject_income(self):
        total = 0
        irs_ded_category = self.env.ref('l10n_pt_hr_payroll.hr_payroll_irs_ded', raise_if_not_found=False)
        if not irs_ded_category:
            return round(total, 2)
        slips = self.env['hr.payslip'].search(
            [('employee_id', '=', self.id), ('state', 'in', ['done', 'paid'])]).filtered(
            lambda s: s.date_from.year == int(self.income_year))
        for slip in slips:
            for line in slip.line_ids:
                if line.salary_rule_id.category_id == irs_ded_category:
                    total += line.amount
        return round(total, 2)

    def _get_total_irs_retention(self):
        total = 0
        irs_ded_category = self.env.ref('l10n_pt_hr_payroll.hr_payroll_irs_ded', raise_if_not_found=False)
        if not irs_ded_category:
            return round(total, 2)
        slips = self.env['hr.payslip'].search(
            [('employee_id', '=', self.id), ('state', 'in', ['done', 'paid'])]).filtered(
            lambda s: s.date_from.year == int(self.income_year))
        for slip in slips:
            for line in slip.line_ids:
                if line.salary_rule_id.category_id == irs_ded_category:
                    total += line.total
        return round(total, 2)

    def _get_total_ss_retention(self):
        total = 0
        slips = self.env['hr.payslip'].search(
            [('employee_id', '=', self.id), ('state', 'in', ['done', 'paid'])]).filtered(
            lambda s: s.date_from.year == int(self.income_year))
        for slip in slips:
            for line in slip.line_ids:
                if line.salary_rule_id.code in ['SS', 'SSVAC', 'SSCHR']:
                    total += line.total
        return round(total, 2)

    def _get_total_exempt_income(self):
        total_exempt_income = 0
        bonus_category = self.env.ref('l10n_pt_hr_payroll.hr_payroll_bonus', raise_if_not_found=False)
        slips = self.env['hr.payslip'].search(
            [('employee_id', '=', self.id), ('state', 'in', ['done', 'paid'])]).filtered(
            lambda s: s.date_from.year == int(self.income_year))
        for slip in slips:
            for line in slip.line_ids:
                if bonus_category and line.salary_rule_id.category_id == bonus_category:
                    total_exempt_income+= line.total
                if line.salary_rule_id.code == 'AC':
                    exempt_value = self.company_id.default_hr_payroll_cost_allowance_moe_exempt_limit if self.moe else self.company_id.default_hr_payroll_cost_allowance_exempt_limit
                    exempt_value = line.slip_id.version_id.cost_allw_amount if line.slip_id.version_id.cost_allw_amount <= exempt_value else exempt_value
                    total_exempt_income += exempt_value * line.quantity
                if line.salary_rule_id.code == 'AC_FOREIGN':
                    exempt_value = self.company_id.default_hr_payroll_foreign_cost_allowance_moe_exempt_limit if line.employee_id.moe else self.company_id.default_hr_payroll_foreign_cost_allowance_exempt_limit
                    total_exempt_income += exempt_value * line.quantity
                if line.salary_rule_id.code == 'KM':
                    exempt_value = self.company_id.default_hr_payroll_km_exempt_limit
                    exempt_value = line.slip_id.version_id.km_value if line.slip_id.version_id.km_value <= exempt_value else exempt_value
                    total_exempt_income += exempt_value * line.quantity
                if line.salary_rule_id.code == 'PERF_BONUS':
                    exempt_amount = self.version_id.wage * 0.06
                    exempt_amount = line.amount if line.amount <= exempt_amount else exempt_amount
                    total_exempt_income += exempt_amount
                if line.salary_rule_id.code == 'FAIL_ALLOW':
                    exempt_amount = ((self.version_id.wage * 14) / 12) * 0.05
                    exempt_amount = line.amount if line.amount <= exempt_amount else exempt_amount
                    total_exempt_income += exempt_amount
        return total_exempt_income

    def _get_total_union_contribution(self):
        total = 0
        slips = self.env['hr.payslip'].search(
            [('employee_id', '=', self.id), ('state', 'in', ['done', 'paid'])]).filtered(
            lambda s: s.date_from.year == int(self.income_year))
        for slip in slips:
            for line in slip.line_ids:
                if line.salary_rule_id.code == 'UNION':
                    total += line.total
        return round(total, 2)

    def _get_report_date(self):
        return fields.date.today()
