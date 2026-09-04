from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    for model_data in env['ir.model.data'].search(
            [('module', '=', 'l10n_pt_reports_arxi'), ('model', 'in', ['account.report.line'])]):
        env['account.report.line'].browse(int(model_data.res_id)).unlink()
        model_data.unlink()
