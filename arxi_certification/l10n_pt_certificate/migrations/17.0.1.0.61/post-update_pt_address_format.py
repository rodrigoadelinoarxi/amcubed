from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    pt = env.ref('base.pt')
    pt.write({'address_format': "%(street)s\n%(street2)s\n%(city)s %(zip)s\n%(country_name)s"})
