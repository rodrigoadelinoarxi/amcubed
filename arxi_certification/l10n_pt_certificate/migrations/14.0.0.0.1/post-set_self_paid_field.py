from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env['account.move'].search([
        ('move_type', '=', 'out_invoice'),
        ('journal_id.document_type_id.code', 'in', ('FR', 'FS')),
        ('state', '!=', 'draft')])
    moves.write({'is_self_paid': True})
