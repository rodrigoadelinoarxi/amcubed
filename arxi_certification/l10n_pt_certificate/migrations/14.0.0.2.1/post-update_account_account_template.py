from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    chart = env.ref('l10n_pt_certificate.pt_chart_template')
    pt_comp = env['res.company'].search([('chart_template_id', '=', chart.id)])

    template_ids = env['account.account.template'].search(
        [('chart_template_id', '=', chart.id), ('tag_ids', '!=', False)]
    )
    for template in template_ids:
        account_ids = env['account.account'].search([('company_id', 'in', pt_comp.ids), ('code', '=', template.code)])
        account_ids.write({'tag_ids': [(4, tag.id) for tag in template.tag_ids]})

