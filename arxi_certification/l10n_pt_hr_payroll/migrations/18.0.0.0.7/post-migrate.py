# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration script to populate insurance_company Many2one field
    based on insurance_company_code for companies and insurance_company_old for employees
    """
    _logger.info("Starting post-migration: populate insurance_company from old data")

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Migrate res.company records using insurance_company_code
    _logger.info("Migrating res.company insurance_company_code to insurance_company")

    # Check if insurance_company_code column exists
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='res_company'
        AND column_name='insurance_company_code'
    """)

    if cr.fetchone():
        _logger.info("insurance_company_code column found, proceeding with migration")

        # First, let's see all companies with insurance_company_code
        cr.execute("""
            SELECT id, insurance_company_code, name, insurance_company
            FROM res_company
            WHERE insurance_company_code IS NOT NULL
            AND insurance_company_code != ''
        """)

        all_companies = cr.fetchall()
        _logger.info(f"Total companies with insurance_company_code: {len(all_companies)}")
        for comp_id, ins_code, comp_name, ins_company in all_companies:
            _logger.info(f"Company: {comp_name}, Code: {ins_code}, Current insurance_company: {ins_company}")

        # Get companies that need migration
        cr.execute("""
            SELECT id, insurance_company_code, name
            FROM res_company
            WHERE insurance_company_code IS NOT NULL
            AND insurance_company_code != ''
            AND (insurance_company IS NULL OR insurance_company = 0)
        """)

        companies_data = cr.fetchall()
        _logger.info(f"Found {len(companies_data)} company records that need migration")

        migrated_count = 0
        for company_id, insurance_code, company_name in companies_data:
            _logger.info(f"Processing company {company_name} with code {insurance_code}")

            insurance = env['hr.insurance.company'].search([
                ('code', '=', insurance_code)
            ], limit=1)

            if insurance:
                _logger.info(f"Found insurance company: {insurance.name} (id: {insurance.id})")
                cr.execute("""
                    UPDATE res_company
                    SET insurance_company = %s
                    WHERE id = %s
                """, (insurance.id, company_id))

                # Verify the update
                cr.execute("SELECT insurance_company FROM res_company WHERE id = %s", (company_id,))
                result = cr.fetchone()
                _logger.info(f"After update, insurance_company = {result[0] if result else 'NULL'}")

                migrated_count += 1
                _logger.info(f"Updated company {company_name} with insurance company {insurance.name}")
            else:
                _logger.warning(f"No insurance company found for code {insurance_code} (company {company_name})")

        _logger.info(f"Migrated {migrated_count} company records")
    else:
        _logger.info("insurance_company_code column not found, skipping company migration")

    # For employees - use the insurance_company_old column created in pre-migrate
    _logger.info("Checking employee insurance_company_old field for migration")

    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='hr_employee'
        AND column_name='insurance_company_old'
    """)

    if cr.fetchone():
        _logger.info("Found insurance_company_old column, attempting employee migration")

        # Get employees with insurance_company_old
        cr.execute("""
            SELECT id, insurance_company_old
            FROM hr_employee
            WHERE insurance_company_old IS NOT NULL
            AND insurance_company_old != ''
        """)

        employees_data = cr.fetchall()
        _logger.info(f"Found {len(employees_data)} employee records to migrate")

        migrated_count = 0
        for emp_id, insurance_value in employees_data:
            insurance = None

            # First, save the old value to insurance_company_name
            cr.execute("""
                UPDATE hr_employee
                SET insurance_company_name = %s
                WHERE id = %s
            """, (insurance_value, emp_id))

            # For employees, prioritize searching by name (not code)
            # Try to match by exact name first (case-insensitive)
            insurance = env['hr.insurance.company'].search([
                ('name', '=ilike', insurance_value)
            ], limit=1)

            # If not found, try partial match
            if not insurance:
                insurance = env['hr.insurance.company'].search([
                    ('name', 'ilike', insurance_value)
                ], limit=1)

            # If still not found, try name containing the value
            if not insurance:
                insurance = env['hr.insurance.company'].search([
                    ('name', 'ilike', f'%{insurance_value}%')
                ], limit=1)

            # As last resort, try to match by code
            if not insurance:
                insurance = env['hr.insurance.company'].search([
                    ('code', '=', insurance_value)
                ], limit=1)

            if insurance:
                cr.execute("""
                    UPDATE hr_employee
                    SET insurance_company = %s
                    WHERE id = %s
                """, (insurance.id, emp_id))
                migrated_count += 1
                _logger.info(f"Matched employee {emp_id} value '{insurance_value}' with insurance company {insurance.display_name}")
            else:
                _logger.warning(f"No insurance company found for value '{insurance_value}' (employee id {emp_id})")

        _logger.info(f"Migrated {migrated_count} employee records")

        # Drop the old column after migration (value is now in insurance_company_name)
        _logger.info("Dropping insurance_company_old column from hr_employee")
        cr.execute("ALTER TABLE hr_employee DROP COLUMN IF EXISTS insurance_company_old")
    else:
        _logger.info("insurance_company_old column not found, skipping employee migration")

    _logger.info("Migration completed: insurance_company population")
