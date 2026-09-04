from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayrollRetroactiveLine(models.Model):
    _name = 'hr.payroll.retroactive.line'
    _description = 'Retroactive Payroll Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    retroactive_id = fields.Many2one('hr.payroll.retroactive', required=True, ondelete='cascade', tracking=True)
    name = fields.Char(tracking=True)
    employee_id = fields.Many2one(related='retroactive_id.employee_id', store=True, readonly=True)
    version_id = fields.Many2one(related='retroactive_id.version_id', store=True, readonly=True)
    origin_month = fields.Date(required=True, tracking=True)
    payment_month = fields.Date(required=True, tracking=True)
    retroactive_type = fields.Selection(related='retroactive_id.retroactive_type', store=True, readonly=True)
    retroactive_state = fields.Selection(related='retroactive_id.state', string='Retroactive State')
    salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        required=True,
        tracking=True,
        domain=[('is_retroactive', '=', True)],
    )
    input_type_id = fields.Many2one(
        'hr.payslip.input.type',
        string='Payslip Input Type',
        required=True,
        tracking=True,
        domain=[('is_retroactive', '=', True)],
    )
    original_rule_id = fields.Many2one(related='salary_rule_id.original_rule_id', store=True, readonly=True)
    amount = fields.Monetary(required=True, tracking=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='version_id.company_id.currency_id', readonly=True)
    natrem_code = fields.Char(string='NATREM Code', tracking=True)
    in_dmr = fields.Boolean(related='salary_rule_id.in_dmr', store=True, readonly=True)
    in_dri = fields.Boolean(related='salary_rule_id.in_dri', store=True, readonly=True)
    in_accounting = fields.Boolean(related='salary_rule_id.in_accounting', store=True, readonly=True)
    use_origin_month_for_dri = fields.Boolean(related='salary_rule_id.use_origin_month_for_dri', store=True, readonly=True)
    allow_negative = fields.Boolean(related='salary_rule_id.allow_negative', store=True, readonly=True)
    communication_state = fields.Selection([
        ('to_communicate', 'To Communicate'),
        ('communicated', 'Communicated'),
        ('error', 'Error'),
        ('excluded', 'Excluded'),
    ], default='to_communicate', tracking=True)
    payslip_input_id = fields.Many2one('hr.payslip.input', tracking=True)
    payslip_line_id = fields.Many2one('hr.payslip.line', tracking=True)
    notes = fields.Text(tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('allow_retroactive_line_state_update'):
            retroactive_ids = [vals.get('retroactive_id') for vals in vals_list if vals.get('retroactive_id')]
            if retroactive_ids:
                retroactives = self.env['hr.payroll.retroactive'].browse(retroactive_ids)
                if any(retroactive.state not in ['draft', 'confirmed'] for retroactive in retroactives):
                    raise ValidationError(_('Retroactive lines can only be added in draft or confirmed state.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('allow_retroactive_line_state_update') and any(
                line.retroactive_id.state not in ['draft', 'confirmed'] for line in self):
            raise ValidationError(_('Retroactive lines can only be modified in draft or confirmed state.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('allow_retroactive_line_state_update') and any(
                line.retroactive_id.state not in ['draft', 'confirmed'] for line in self):
            raise ValidationError(_('Retroactive lines can only be removed in draft or confirmed state.'))
        return super().unlink()

    @api.onchange('salary_rule_id')
    def _onchange_salary_rule_id(self):
        if self.salary_rule_id:
            input_type = self.salary_rule_id.retroactive_input_type_id
            if not input_type:
                input_type = self.env['hr.payslip.input.type'].search([
                    ('code', '=', self.salary_rule_id.code),
                    ('is_retroactive', '=', True),
                ], limit=1)
            self.input_type_id = input_type.id
            self.natrem_code = self.salary_rule_id.natrem_code

    @api.constrains('origin_month', 'payment_month', 'amount', 'salary_rule_id', 'input_type_id')
    def _check_line_values(self):
        for rec in self:
            if not rec.origin_month:
                raise ValidationError(_('Origin month is required.'))
            if not rec.payment_month:
                raise ValidationError(_('Payment month is required.'))
            if not rec.input_type_id:
                raise ValidationError(_('Payslip input type is required.'))
            if not rec.input_type_id.is_retroactive:
                raise ValidationError(_('Payslip input type must be marked as retroactive.'))
            if rec.origin_month and rec.payment_month and rec.origin_month > rec.payment_month:
                raise ValidationError(_('Origin month cannot be after the payment month.'))
            if rec.in_dri and not rec.natrem_code:
                raise ValidationError(_('Retroactive lines used in DRI must define a NATREM code.'))
            if rec.amount < 0 and not rec.allow_negative:
                raise ValidationError(_('Negative amounts are not allowed for this retroactive line.'))
            if rec.natrem_code == '6' and rec.amount < 0 and not rec.allow_negative:
                raise ValidationError(_('NATREM 6 lines cannot be negative unless negative values are allowed.'))
