from odoo import api, _, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    template = env.ref('account.email_template_edi_invoice')
    template.report_template_ids = [(6, 0, env.ref('account.account_invoices_without_payment').ids)]
