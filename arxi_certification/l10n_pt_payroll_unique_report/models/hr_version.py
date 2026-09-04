from odoo import models, fields


class HrVersion(models.Model):
    _inherit = 'hr.version'

    contract_type = fields.Many2one('unique.report.table.13', string='Contract Type (Unique Report)')
    entry_reason = fields.Many2one('unique.report.table.26', string='Entry Reason')
    exit_reason = fields.Many2one('unique.report.table.27', string='Exit Reason')