from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_l10n_pt_hr_payroll_split_analytic = fields.Boolean(
        related='company_id.payroll_split_analytic_enabled',
        readonly=False,
        string="Apply analytics only to specific accounts",
        help="When enabled, payroll analytics are applied by salary-rule side configuration "
             "(debit and/or credit) on Portuguese payroll structures.",
    )

    def execute(self):
        apply_split_defaults = bool(self.module_l10n_pt_hr_payroll_split_analytic)
        result = super().execute()
        if not apply_split_defaults:
            return result

        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'l10n_pt_hr_payroll_split_analytic')],
            limit=1,
        )
        if module.state != 'installed':
            return result

        companies = self.env['res.company'].sudo().search([('payroll_split_analytic_enabled', '=', True)])
        for company in companies:
            if hasattr(type(company), '_apply_payroll_analytic_rule_defaults'):
                company._apply_payroll_analytic_rule_defaults()
        return result
