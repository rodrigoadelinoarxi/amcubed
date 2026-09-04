from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    :return:
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    saphety_edi_format = env['account.edi.format'].search([('code', '=', 'saphety_pt')], limit=1)

    if saphety_edi_format:
        partners = env['res.partner'].search([])
        for partner in partners:
            if 'saphety_pt' not in partner.edi_format_ids.mapped('code'):
                partner.write({
                    'edi_format_ids': [(4, saphety_edi_format.id)]
                })
