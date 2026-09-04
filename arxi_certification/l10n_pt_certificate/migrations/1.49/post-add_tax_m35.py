from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Guarantee the M35 exemption (Art.º 2.º, n.º 1, alínea j) do CIVA) exists
    on existing databases.

    The M35 exemption is in data/account_tax_exemption.xml under noupdate="1",
    which loads on a fresh install but NOT on an upgrade — so create it here
    (idempotently, with its xml-id) for existing databases. The M35 taxes
    themselves are created from the chart template by l10n_pt_reports_arxi's
    1.43 post-migration, which runs after that module's grid-tag @template is
    registered (this module loads first, so it cannot apply those tags here).
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    exemption_m35 = env.ref('l10n_pt_certificate.m35', raise_if_not_found=False)
    if exemption_m35:
        return

    exemption_m35 = env['account.tax.exemption'].search([('code', '=', 'M35')], limit=1)
    if not exemption_m35:
        exemption_m35 = env['account.tax.exemption'].create({
            'name': 'VAT - Reverse Charge',
            'code': 'M35',
            'description': 'Artigo 2.º, n.º 1, alínea j) do CIVA',
            'country_id': env.ref('base.pt').id,
        })
    env['ir.model.data'].create({
        'module': 'l10n_pt_certificate',
        'name': 'm35',
        'model': 'account.tax.exemption',
        'res_id': exemption_m35.id,
        'noupdate': True,
    })
