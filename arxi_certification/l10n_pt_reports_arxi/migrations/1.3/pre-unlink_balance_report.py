from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if report := env.ref('l10n_pt_reports_arxi.balance_sheet'):
        report.unlink()
    if report := env.ref('l10n_pt_reports_arxi.tax_report_pt_anexo_clientes'):
        report.unlink()