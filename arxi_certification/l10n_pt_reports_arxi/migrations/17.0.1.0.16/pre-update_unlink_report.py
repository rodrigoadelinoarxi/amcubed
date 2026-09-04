from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if report := env.ref('l10n_pt_reports_arxi.statement_of_changes_in_equity'):
        report.unlink()