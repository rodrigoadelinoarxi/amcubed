from odoo import api, _, SUPERUSER_ID


def migrate(cr, version):
    cr.execute("""ALTER TABLE account_move ADD COLUMN IF NOT EXISTS "tax_report_refund_type_customer" int4""")
    cr.execute("""ALTER TABLE account_move ADD COLUMN IF NOT EXISTS "tax_report_refund_type_supplier" int4""")
    cr.execute(""" UPDATE account_move SET tax_report_refund_type_customer = tax_report_refund_type WHERE move_type = 'out_refund'""")
    cr.execute(""" UPDATE account_move SET tax_report_refund_type_supplier = tax_report_refund_type WHERE move_type = 'in_refund'""")