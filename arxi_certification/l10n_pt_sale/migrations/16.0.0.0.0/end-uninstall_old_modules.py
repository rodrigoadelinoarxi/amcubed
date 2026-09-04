from odoo import api, SUPERUSER_ID
from odoo.tools import plaintext2html


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ir.module.module'].search([
        ('name', '=', 'product_matrix_restrict_negative_values')
    ]).write({'state': 'to remove'})
