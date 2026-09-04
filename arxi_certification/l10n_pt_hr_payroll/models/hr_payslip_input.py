from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    retroactive_id = fields.Many2one('hr.payroll.retroactive', string='Retroactive Adjustment')
    retroactive_line_id = fields.Many2one('hr.payroll.retroactive.line', string='Retroactive Line')
    origin_month = fields.Date(string='Origin Month')
    payment_month = fields.Date(string='Payment Month')
    natrem_code = fields.Char(string='NATREM Code')
    retroactive_type = fields.Selection([
        ('wage', 'Wage'),
        ('allowance', 'Allowance'),
        ('absence', 'Absence / Deduction'),
        ('extra_hours', 'Extra Hours'),
        ('manual', 'Manual'),
    ])
    processing_mode = fields.Selection([
        ('open_payslip', 'Open Payslip'),
        ('extraordinary', 'Extraordinary Payslip'),
    ], default='open_payslip')
    communication_state = fields.Selection([
        ('to_communicate', 'To Communicate'),
        ('communicated', 'Communicated'),
        ('error', 'Error'),
        ('excluded', 'Excluded'),
    ], default='to_communicate')

    @api.onchange('amount')
    def _check_negative_amount(self):
        """
        Prevent negative amounts in inputs, except for correction inputs.
        Correction inputs (BASIC_CORR_DAYS, etc.) can have negative values
        to represent deductions.
        """
        correction_input_codes = ['BASIC_CORR_DAYS', 'MEAL_CORR_DAYS', 'VAC_CORR_DAYS', 'CHR_CORR_DAYS']

        for rec in self:
            if rec.amount < 0:
                # Allow negative values for correction inputs
                is_correction = rec.input_type_id and rec.input_type_id.code in correction_input_codes
                is_retroactive = bool(
                    (rec.retroactive_line_id and rec.retroactive_line_id.salary_rule_id.allow_negative)
                    or (rec.retroactive_id and rec.retroactive_id.salary_rule_id.allow_negative)
                )

                if not is_correction and not is_retroactive:
                    raise ValidationError(_('Line Amount cannot be negative.'))
