from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    env['ir.model.data'].search([
        ('module', '=', 'l10n_pt_certificate'),
        ('model', '=', 'account.tax.template')
    ]).write({'noupdate': False})
