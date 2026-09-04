from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    report_ids = [
        'sale.report_saleorder',
        'sale.report_saleorder_pro_forma'
    ]
    for report in report_ids:
        report_id = env['ir.actions.report'].search([('report_name', '=', report)], limit=1)
        report_id.protected = True
