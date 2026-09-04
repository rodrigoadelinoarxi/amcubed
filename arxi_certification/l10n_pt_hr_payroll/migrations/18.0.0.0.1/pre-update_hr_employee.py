from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration script to move data from deprecated custom fields to standard Odoo fields.
    This migration is necessary for V17 to V18 upgrade of l10n_pt_hr_payroll module.

    Migrations performed:
    1. handycap -> disabled (custom field to standard Odoo field)
    2. ssn -> ssnid (custom field to standard Odoo field)
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # ==================== Migration 1: handycap -> disabled ====================
    _logger.info("Starting migration: handycap -> disabled field for hr.employee")

    # Check if the handycap column exists in the database
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='hr_employee' AND column_name='handycap'
    """)

    if cr.fetchone():
        _logger.info("Found 'handycap' column in hr_employee table. Starting data migration...")

        # Migrate data from handycap to disabled field
        # Only update records where handycap is True and disabled is False or NULL
        cr.execute("""
            UPDATE hr_employee
            SET disabled = handycap
            WHERE handycap = TRUE
            AND (disabled IS NULL OR disabled = FALSE)
        """)

        affected_rows = cr.rowcount
        _logger.info(f"Migration completed: {affected_rows} employee(s) updated with disabled field from handycap field")

        # Drop the handycap column after migration
        # Note: This will be handled by Odoo's ORM automatically when the field is removed from the model
        # We don't drop it here to allow for rollback if needed
        _logger.info("Migration successful. The 'handycap' column will be removed by Odoo ORM on next update.")
    else:
        _logger.info("Column 'handycap' not found. Migration may have already been completed or is not needed.")

    # ==================== Migration 2: ssn -> ssnid ====================
    _logger.info("Starting migration: ssn -> ssnid field for hr.employee")

    # Check if the ssn column exists in the database
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='hr_employee' AND column_name='ssn'
    """)

    if cr.fetchone():
        _logger.info("Found 'ssn' column in hr_employee table. Starting data migration...")

        # Migrate data from ssn to ssnid field
        # Only update records where ssn has a value and ssnid is empty or NULL
        cr.execute("""
            UPDATE hr_employee
            SET ssnid = ssn
            WHERE ssn IS NOT NULL
            AND ssn != ''
            AND (ssnid IS NULL OR ssnid = '')
        """)

        affected_rows = cr.rowcount
        _logger.info(f"Migration completed: {affected_rows} employee(s) updated with ssnid field from ssn field")

        # Drop the ssn column after migration
        # Note: This will be handled by Odoo's ORM automatically when the field is removed from the model
        # We don't drop it here to allow for rollback if needed
        _logger.info("Migration successful. The 'ssn' column will be removed by Odoo ORM on next update.")
    else:
        _logger.info("Column 'ssn' not found. Migration may have already been completed or is not needed.")

    _logger.info("All migration scripts completed successfully")
