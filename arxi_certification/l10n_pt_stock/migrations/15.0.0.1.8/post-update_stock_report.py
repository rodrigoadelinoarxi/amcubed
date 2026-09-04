from odoo import api, SUPERUSER_ID
from odoo.tools import plaintext2html


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for transport in env['pt.transport'].search([('note', '!=', False)]):
        transport.note = plaintext2html(transport.note)
