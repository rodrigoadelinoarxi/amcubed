from odoo import models, fields, api


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    training_frequency = fields.Many2one('unique.report.table.28', string='Training Frequency')
    training_ref_period = fields.Many2one('unique.report.table.29', string='Training Reference Period')
    training_area = fields.Many2one('unique.report.table.30', string='Training Area')
    training_type = fields.Many2one('unique.report.table.31', string='Training Type')
    training_initiative = fields.Many2one('unique.report.table.32', string='Training Initiative')
    training_schedule = fields.Many2one('unique.report.table.33', string='Training Schedule')
    training_entity = fields.Many2one('unique.report.table.34', string='Training Entity')
    training_certificate_type = fields.Many2one('unique.report.table.35', string='Training Certificate Type')
    training_qualification_level = fields.Many2one('unique.report.table.36', string='Training Qualification Level')

    is_training = fields.Boolean(string='Is Training', default=False, compute='_is_training')

    is_strike = fields.Boolean(string='Is Strike', default=False, compute='_is_strike')
    strike_code = fields.Char(string='Strike Code')
    strike_claim = fields.Many2one('unique.report.table.52', string='Strike Claim')
    strike_result = fields.Many2one('unique.report.table.53', string='Strike Result')

    @api.depends('holiday_status_id')
    def _is_training(self):
        for record in self:
            record.is_training = record.holiday_status_id.is_training

    @api.depends('holiday_status_id')
    def _is_strike(self):
        for record in self:
            record.is_strike = record.holiday_status_id.is_strike

    def _prepare_employees_holiday_values(self, employees):
        values_list = super()._prepare_employees_holiday_values(employees)

        for vals in values_list:
            vals.update({
                'strike_code'  : self.strike_code,
                'strike_claim' : self.strike_claim.id if self.strike_claim else False,
                'strike_result': self.strike_result.id if self.strike_result else False,
            })

        return values_list
