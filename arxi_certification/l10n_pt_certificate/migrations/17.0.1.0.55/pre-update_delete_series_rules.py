from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref('l10n_pt_certificate.account_series_company_rule')
    rule_line = env.ref('l10n_pt_certificate.account_series_line_company_rule')
    rule.unlink()
    rule_line.unlink()