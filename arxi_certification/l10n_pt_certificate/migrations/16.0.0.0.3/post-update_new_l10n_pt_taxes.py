from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    This migration will create new account taxes based on the new tax exemptions for 2023.
    This will also archive the exemption taxes that should not be used after 2023.
    :return:
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    new_tax_templates = env['account.tax.template'].search([
        ('exemption_id.code', 'in', (
            'M19', 'M20', 'M21', 'M25', 'M30', 'M31', 'M32', 'M33', 'M40', 'M41', 'M42', 'M43'
        )),
        ('chart_template_id', '=', env.ref('l10n_pt_certificate.pt_chart_template').id)
    ], order='exemption_id desc')

    for company in env['res.company'].search([('chart_template_id', '=', env.ref('l10n_pt_certificate.pt_chart_template').id)]):
        last_exempt_tax_sequence = env['account.tax'].search([
            ('company_id', '=', company.id),
            ('exemption_id', '!=', False),
            ('type_tax_use', '=', 'sale')
        ])[-1].sequence
        tax_template_vals = []
        for template in new_tax_templates:
            vals = template._get_tax_vals(company, {})
            vals.update({
                'sequence'  : last_exempt_tax_sequence + 1,  # Create taxes in the last position
                'country_id': template.chart_template_id.country_id.id,
            })

            tax_template_vals.append((template, vals))
        # Create new taxes
        env.ref('l10n_pt_certificate.pt_chart_template').with_context(
            dict(self.env.context, performing_migration=True))._create_records_with_xmlid(
            'account.tax', tax_template_vals, company
        )
        # Archive deprecated taxes
        env['account.tax'].search([
            ('exemption_id.code', 'in', ('M03', 'M08')),
            ('company_id', '=', company.id)
        ]).write({'active': False})
