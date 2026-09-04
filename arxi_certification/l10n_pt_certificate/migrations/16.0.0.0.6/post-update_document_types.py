from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    :return:
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    env['account.document.type'].search([
        ('code', 'in', ('FT', 'FR', 'FS', 'NC'))
    ]).write({'category': 'invoicing'})
    env['account.document.type'].search([('code', 'in', ('FT', 'FR', 'FS', 'NC'))]).write({'category': 'invoicing'})
