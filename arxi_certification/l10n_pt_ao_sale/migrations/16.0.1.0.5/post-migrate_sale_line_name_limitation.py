import odoo
from odoo import api, _, SUPERUSER_ID


def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE sale_order_line 
        DROP CONSTRAINT sale_order_line_check_name_size
        """
    )

