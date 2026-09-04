# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return

    # Update default_hr_payroll_food_val_exempt_limit: 6.0 -> 6.15
    cr.execute("""
        UPDATE res_company
        SET default_hr_payroll_food_val_exempt_limit = 6.15
        WHERE default_hr_payroll_food_val_exempt_limit = 6.0
    """)

    # Update default_hr_payroll_food_val_card_exempt_limit: 10.20 -> 10.46
    cr.execute("""
        UPDATE res_company
        SET default_hr_payroll_food_val_card_exempt_limit = 10.46
        WHERE default_hr_payroll_food_val_card_exempt_limit = 10.20
    """)

    # Update annual_youth_irs_limit: 28737.50 -> 29542.15
    cr.execute("""
        UPDATE res_company
        SET annual_youth_irs_limit = 29542.15
        WHERE annual_youth_irs_limit = 28737.50
    """)
