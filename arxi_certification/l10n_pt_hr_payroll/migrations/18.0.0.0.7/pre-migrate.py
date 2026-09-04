# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migration script to prepare for insurance_company field type change
    from Char to Many2one
    """
    _logger.info("Starting pre-migration: prepare insurance_company field migration")

    # For hr_employee: rename old insurance_company (Char) to insurance_company_old
    # so we can preserve the data and later match it
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='hr_employee'
        AND column_name='insurance_company'
    """)

    if cr.fetchone():
        _logger.info("Renaming hr_employee.insurance_company to insurance_company_old")
        cr.execute("""
            ALTER TABLE hr_employee
            RENAME COLUMN insurance_company TO insurance_company_old
        """)
        _logger.info("Renamed hr_employee.insurance_company column")

    # For res_company: the insurance_company_code already exists and will be used
    # No need to rename anything here as we're keeping insurance_company_code

    _logger.info("Pre-migration completed")
