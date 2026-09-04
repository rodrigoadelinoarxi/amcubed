from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class HrPayrollRetroactive(models.Model):
    _name = 'hr.payroll.retroactive'
    _description = 'Payroll Retroactive Adjustment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, default='Retroactive Adjustment', tracking=True)
    employee_id = fields.Many2one('hr.employee', required=True, tracking=True)
    version_id = fields.Many2one(
        'hr.version',
        required=True,
        tracking=True,
        domain="[('employee_id', '=', employee_id), ('is_current', '=', True)]",
    )
    retroactive_type = fields.Selection([
        ('wage', 'Wage'),
        ('allowance', 'Allowance'),
        ('absence', 'Absence / Deduction'),
        ('extra_hours', 'Extra Hours'),
        ('manual', 'Manual'),
    ], required=True, tracking=True)
    salary_rule_id = fields.Many2one('hr.salary.rule', tracking=True)
    processing_mode = fields.Selection([
        ('open_payslip', 'Open Payslip'),
        ('extraordinary', 'Extraordinary Payslip'),
    ], default='open_payslip', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('processed', 'Processed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    notes = fields.Text(tracking=True)
    payslip_id = fields.Many2one('hr.payslip', tracking=True)
    input_id = fields.Many2one('hr.payslip.input', tracking=True)
    line_ids = fields.One2many('hr.payroll.retroactive.line', 'retroactive_id', string='Lines')
    currency_id = fields.Many2one(related='version_id.company_id.currency_id', readonly=True)
    communication_state = fields.Selection([
        ('to_communicate', 'To Communicate'),
        ('communicated', 'Communicated'),
        ('error', 'Error'),
        ('excluded', 'Excluded'),
    ], default='to_communicate', tracking=True)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.version_id = self.employee_id._get_version(fields.Date.today())

    @api.constrains('salary_rule_id', 'line_ids')
    def _check_values(self):
        for rec in self:
            if rec.salary_rule_id:
                if not rec.salary_rule_id.is_retroactive:
                    raise ValidationError(_('The selected salary rule must be marked as retroactive.'))
                if not rec.salary_rule_id.natrem_code:
                    raise ValidationError(_('The selected salary rule must define a NATREM code.'))
                if rec.salary_rule_id.in_dri and not rec.salary_rule_id.use_origin_month_for_dri:
                    raise ValidationError(_('Retroactive rules used in DRI must use the origin month.'))
            if not rec.line_ids:
                raise ValidationError(_('Please define at least one retroactive line.'))

    def action_confirm(self):
        payslips = self.env['hr.payslip']
        for retro in self:
            lines = retro.line_ids or self.env['hr.payroll.retroactive.line']
            if not lines:
                raise ValidationError(_('Please create one or more retroactive lines.'))
            for line in lines:
                slip = retro._get_target_payslip(line.payment_month)
                if not slip:
                    raise ValidationError(_('No open payslip found for the payment month.'))
                payslips |= slip
                input_line = self.env['hr.payslip.input'].create({
                    'payslip_id': slip.id,
                    'input_type_id': line.input_type_id.id,
                    'name': line.name or retro.name,
                    'code': line.input_type_id.code,
                    'amount': line.amount,
                    'retroactive_id': retro.id,
                    'retroactive_line_id': line.id,
                    'origin_month': line.origin_month,
                    'payment_month': line.payment_month,
                    'natrem_code': line.natrem_code,
                    'retroactive_type': line.retroactive_type,
                    'processing_mode': retro.processing_mode,
                    'communication_state': line.communication_state,
                })
                line.write({'payslip_input_id': input_line.id})
            retro.write({'state': 'confirmed'})
        return self._action_open_payslips(payslips)

    def _action_open_payslips(self, payslips):
        if not payslips:
            return True
        action = self.env['ir.actions.actions']._for_xml_id('hr_payroll.action_view_hr_payslip_form')
        if len(payslips) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': payslips.id,
                'views': [(False, 'form')],
            })
        else:
            action.update({
                'domain': [('id', 'in', payslips.ids)],
                'views': [(False, 'list'), (False, 'form')],
            })
        return action

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def _get_target_payslip(self, payment_date):
        self.ensure_one()
        if self.processing_mode == 'extraordinary':
            return self._get_or_create_extraordinary_payslip(payment_date)

        slip = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['draft', 'verify']),
            ('payslip_type', '!=', 'extraordinary'),
            ('date_from', '<=', payment_date),
            ('date_to', '>=', payment_date),
        ], limit=1)
        if slip:
            return slip
        return False

    def _get_or_create_extraordinary_payslip(self, payment_date):
        self.ensure_one()
        date_from = payment_date.replace(day=1)
        date_to = payment_date + relativedelta(day=31)
        slip = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['draft', 'verify']),
            ('payslip_type', '=', 'extraordinary'),
            ('date_from', '=', date_from),
            ('date_to', '=', date_to),
        ], limit=1)
        if slip:
            return slip

        last_slip = self.env['hr.payslip'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['done', 'paid']),
        ], order='date_to desc', limit=1)
        struct = last_slip.struct_id or self.version_id.structure_type_id.default_struct_id
        if not struct:
            raise ValidationError(_('No payroll structure found to create the extraordinary payslip.'))

        slip = self.env['hr.payslip'].create({
            'name': _('New Payslip'),
            'employee_id': self.employee_id.id,
            'version_id': self.version_id.id,
            'struct_id': struct.id,
            'date_from': date_from,
            'date_to': date_to,
            'entries_date_from': date_from,
            'entries_date_to': date_to,
            'payslip_type': 'extraordinary',
        })
        slip._compute_name()
        return slip
