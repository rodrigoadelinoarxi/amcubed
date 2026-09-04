from odoo import api, _, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    bank_journals = env['account.journal'].search([('type', 'in', ['bank', 'cash'])])
    tuple_bank_journals = tuple(bank_journals.ids)
    cr.execute("UPDATE account_journal SET l10n_cert = True where id in %s" % str(tuple_bank_journals))
