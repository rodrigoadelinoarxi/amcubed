from odoo import fields, models, api
import calendar

MONTHS = [(str(month).zfill(2), month_name) for month, month_name in enumerate(calendar.month_name) if month != 0]


class ResCompany(models.Model):
    _inherit = 'res.company'

    default_hr_payroll_food_val = fields.Monetary(default=6.00, tracking=True, currency_field='currency_id')
    default_hr_payroll_food_val_exempt_limit = fields.Monetary(default=6.15, tracking=True, currency_field='currency_id')
    default_hr_payroll_food_val_card_exempt_limit = fields.Monetary(default=10.46, tracking=True,
                                                                    currency_field='currency_id')

    default_hr_payroll_km_val = fields.Monetary(default=0.40, tracking=True, currency_field='currency_id')
    default_hr_payroll_km_exempt_limit = fields.Monetary(default=0.40, tracking=True, currency_field='currency_id')

    default_hr_payroll_cost_allowance_daily_val = fields.Monetary(default=65.89, tracking=True,
                                                                  currency_field='currency_id')
    default_hr_payroll_cost_allowance_exempt_limit = fields.Monetary(default=65.89, tracking=True,
                                                                     currency_field='currency_id')
    default_hr_payroll_cost_allowance_moe_exempt_limit = fields.Monetary(default=72.65, tracking=True,
                                                                         currency_field='currency_id')

    niss = fields.Char(string="Social Security Number", help="Social Security beneficiary number.", tracking=True)
    finance_service_code = fields.Char(tracking=True)
    legal_rep_nif = fields.Char(string="Legal Representant:", tracking=True)
    accountant_nif = fields.Char(string="Certified Accountant:", tracking=True)
    company_type = fields.Selection([
        ('lucrative', 'For-profit entity'),
        ('ipss', 'IPSS'),
        ('other', 'Other non-profit entites'),
    ], default='lucrative', tracking=True)
    insurance_company = fields.Many2one('hr.insurance.company', string='Insurance Company', tracking=True)
    insurance_company_code = fields.Char(string='Insurance Company Code', tracking=True)
    insurance_policy_number = fields.Char(tracking=True)

    @api.onchange('insurance_company')
    def _onchange_insurance_company(self):
        if self.insurance_company:
            self.insurance_company_code = self.insurance_company.code

    default_hr_payroll_foreign_cost_allowance_daily_val = fields.Monetary(
        string="Daily Value for Foreign Cost Allowance",
        default=148.91, tracking=True,
        currency_field='currency_id')
    default_hr_payroll_foreign_cost_allowance_exempt_limit = fields.Monetary(
        string="Exemption Limit for Foreign Cost Allowance", default=148.91, tracking=True,
        currency_field='currency_id')
    default_hr_payroll_foreign_cost_allowance_moe_exempt_limit = fields.Monetary(
        string="Exemption Limit for Foreign Cost Allowance (MOE)", default=167.07, tracking=True,
        currency_field='currency_id')

    work_accident_coefficient = fields.Float(string="Work Accident Coefficient", tracking=True)

    additional_message = fields.Html()
    default_vacation_days = fields.Float(default=22, tracking=True)

    exemption_schedule_percentage = fields.Float(string="Exemption Schedule Percentage", default=0.25, tracking=True)
    night_work_percentage = fields.Float(string="Night Work Percentage", default=0.25, tracking=True)

    annual_youth_irs_limit = fields.Monetary(string="Annual Youth IRS Limit", default=29542.15, tracking=True,
                                             currency_field='currency_id')

    payroll_split_analytic_enabled = fields.Boolean(
        string="Apply analytics only to specific accounts",
        help="When enabled, payroll analytics are applied by salary-rule side configuration "
             "(debit and/or credit) on Portuguese payroll structures.",
        tracking=True,
    )

    food_allw_payment_type = fields.Selection(
        [('normal', 'Normal'), ('fixed_days', 'Fixed Days'), ('fixed_days_discounting', 'Fixed Days with discounts')],
        default='normal', tracking=True, required=True)

    food_allw_discount_month = fields.Selection(MONTHS, string='Month to Discount Food Allowance', tracking=True)

    food_allw_max_days = fields.Float(string="Maximum Days for Food Allowance", default=22, tracking=True)
