from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    report = env['ir.actions.report'].search([('report_name', '=', 'stock.report_deliveryslip')], limit=1)
    report.protected = True
