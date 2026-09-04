from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    local_unit_number = fields.Char(string='Local Unit Number')
    main_activity_cae = fields.Many2one('unique.report.table.4', string='Main Activity CAE')
    legal_nature = fields.Many2one('unique.report.table.7', string='Legal Nature')
    municipality = fields.Many2one('unique.report.table.3', string='Municipality')