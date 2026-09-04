from odoo import models, fields


class InputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    active = fields.Boolean(default=True)
    is_retroactive = fields.Boolean(string='Is Retroactive', default=False)
