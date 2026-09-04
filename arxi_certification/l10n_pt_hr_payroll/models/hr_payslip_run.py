from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

SUBSIDY_RUBRICS = {
    'christmas_allowance': {
        'month_field': 'month_selection_chr',
        'distribution_field': 'christmas',
        'line_codes': ('SN', 'CHR_ALLW'),
    },
    'vacation_allowance': {
        'month_field': 'month_selection_vac',
        'distribution_field': 'vacation',
        'line_codes': ('SF', 'VAC_ALLW'),
    },
}


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    payslip_type = fields.Selection([
        ('normal', 'Normal'),
        ('extraordinary', 'Extraordinary'),
    ], string="Payslip Type:", required=True, default='normal', tracking=True)
    extraordinary_rubric = fields.Selection([
        ('bonus', 'Bonus'),
        ('christmas_allowance', 'Christmas Allowance'),
        ('vacation_allowance', 'Vacation Allowance'),
    ], string='Extraordinary Rubric', tracking=True)
    bonus_application_rule = fields.Selection([
        ('general', 'General'),
        ('per_employee', 'Per Employee'),
    ], string='Application Rule', tracking=True)
    bonus_value_type = fields.Selection([
        ('fixed', 'Fixed Value'),
        ('percentage', 'Percentage of Base Wage'),
    ], string='Value Type', tracking=True)
    bonus_general_amount = fields.Monetary(string='General Value', currency_field='currency_id', tracking=True)
    bonus_general_percentage = fields.Float(string='General Percentage', tracking=True)

    @api.constrains('payslip_type', 'extraordinary_rubric', 'bonus_application_rule', 'bonus_value_type',
                    'bonus_general_amount', 'bonus_general_percentage')
    def _check_extraordinary_config(self):
        for run in self:
            if run.payslip_type != 'extraordinary':
                continue
            if not run.extraordinary_rubric:
                raise ValidationError(_('Please select the extraordinary rubric for the batch.'))
            if run.extraordinary_rubric == 'bonus':
                if not run.bonus_application_rule:
                    raise ValidationError(_('Please select the application rule for the bonus.'))
                if not run.bonus_value_type:
                    raise ValidationError(_('Please select the value type for the bonus.'))
                if run.bonus_application_rule == 'general':
                    if run.bonus_value_type == 'fixed' and not run.bonus_general_amount:
                        raise ValidationError(_('Please fill in the general value to apply to all employees.'))
                    if run.bonus_value_type == 'percentage' and not run.bonus_general_percentage:
                        raise ValidationError(_('Please fill in the general percentage to apply to all employees.'))

    def _get_extraordinary_ineligible_reason(self, employee, version):
        """Returns the reason why the employee cannot be included in this
        extraordinary batch, or False when the employee is eligible."""
        self.ensure_one()
        if not version or not version.is_current:
            return _('No active contract for the period.')
        if not self.env['hr.payslip'].search_count([
            ('employee_id', '=', employee.id),
            ('payslip_type', '=', 'normal'),
            ('state', 'in', ['done', 'paid']),
            ('date_from', '>=', self.date_start),
            ('date_to', '<=', self.date_end),
        ]):
            return _('No validated normal payslip for the period.')
        rubric = SUBSIDY_RUBRICS.get(self.extraordinary_rubric)
        if rubric:
            if contract[rubric['distribution_field']] == 'com_dist_total':
                return _('The allowance is fully distributed in twelfths.')
            if contract[rubric['month_field']] != 'paid_separately':
                return _('The employee is not configured for separate payment of this allowance.')
            if self._is_subsidy_already_processed(employee):
                return _('The allowance was already processed for the selected period.')
        if self.extraordinary_rubric == 'bonus' and self.bonus_value_type == 'percentage' and not contract.wage:
            return _('No base wage defined on the contract.')
        return False

    def _is_subsidy_already_processed(self, employee):
        """Whether the "paid separately" part of the allowance was already
        paid to the employee this year through another extraordinary batch.

        Only extraordinary payslips are considered: the monthly twelfth (or
        half-twelfth) portion of the allowance, paid on normal payslips, is
        a different amount and must not block the batch that pays the
        remaining "paid separately" part (e.g. 1/2 in twelfths + 1/2 paid
        separately)."""
        self.ensure_one()
        rubric = SUBSIDY_RUBRICS.get(self.extraordinary_rubric)
        if not rubric:
            return False
        year = self.date_start.year
        return bool(self.env['hr.payslip.line'].search_count([
            ('slip_id.employee_id', '=', employee.id),
            ('slip_id.payslip_type', '=', 'extraordinary'),
            ('slip_id.state', '!=', 'cancel'),
            ('slip_id', 'not in', self.slip_ids.ids),
            ('slip_id.date_from', '>=', date(year, 1, 1)),
            ('slip_id.date_to', '<=', date(year, 12, 31)),
            ('code', 'in', rubric['line_codes']),
            ('total', '>', 0),
        ]))

    def action_validate(self):
        for run in self.filtered(lambda r: r.payslip_type == 'extraordinary'
                                 and r.extraordinary_rubric in SUBSIDY_RUBRICS):
            for slip in run.slip_ids.filtered(lambda s: s.state != 'cancel'):
                if run._is_subsidy_already_processed(slip.employee_id):
                    raise ValidationError(_(
                        'The allowance of employee %s was already processed for the selected period.',
                        slip.employee_id.name))
        return super().action_validate()

    def action_payslips_send(self):
        self.ensure_one()
        for slip in self.slip_ids:
            slip.force_payslip_send()
