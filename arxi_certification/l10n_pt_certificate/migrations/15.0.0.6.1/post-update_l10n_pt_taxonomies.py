from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    for taxonomy in env['account.taxonomy'].search([]):
        for prefix in taxonomy.account_prefix_ids:
            accounts = env['account.account'].search([
                ('company_id.country_code', '=', 'PT'),
                ('code', '=like', prefix.name + '%')
            ])
            accounts and accounts.write({'taxonomy_id': taxonomy.id})
