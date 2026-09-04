from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Update chart_template from 'pt_certificate' to 'pt_arxi' for Portuguese companies."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    # v19: `res.company.country_id` passou a ser computed sem store (`_compute_address`),
    # logo nao pode ser usado num dominio de search. O `partner_id` continua stored, por
    # isso o pais e alcancado atraves dele.
    env['res.company'].search([
        ('partner_id.country_id.code', '=', 'PT'),
        ('chart_template', '=', 'pt_certificate')
    ]).write({'chart_template': 'pt_arxi'})
