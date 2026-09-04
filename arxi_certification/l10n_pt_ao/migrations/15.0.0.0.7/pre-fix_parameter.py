from odoo import api, _, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('l10n_pt_ao.max_comment_section').write({'key': 'l10n_pt_ao.max_comment_section'})
