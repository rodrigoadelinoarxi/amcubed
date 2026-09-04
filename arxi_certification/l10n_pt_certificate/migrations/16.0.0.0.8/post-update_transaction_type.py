from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    :return:
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    env['account.move'].search([('l10n_pt_transaction_type', '=', False)]).write({'l10n_pt_transaction_type': 'N'})
