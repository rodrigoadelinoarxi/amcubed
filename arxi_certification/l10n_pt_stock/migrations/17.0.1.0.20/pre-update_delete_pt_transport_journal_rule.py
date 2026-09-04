from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref('l10n_pt_stock.pt_transport_journal_rule')
    rule.unlink()
