from odoo import fields, models


class HrSalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    active = fields.Boolean(default=True)
