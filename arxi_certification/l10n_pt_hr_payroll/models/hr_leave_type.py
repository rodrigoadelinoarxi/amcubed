from odoo import models, fields


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    is_training = fields.Boolean(string='Is Training', default=False)
    is_strike = fields.Boolean(string='Is Strike', default=False)