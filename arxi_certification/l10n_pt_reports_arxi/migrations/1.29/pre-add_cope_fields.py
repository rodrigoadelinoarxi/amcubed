"""
Pre-migration script to add COPE fields to account_move table.

This script adds the columns directly in SQL to avoid triggering
compute methods on all existing records during module upgrade.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add COPE fields to account_move table if they don't exist."""
    _logger.info("Starting pre-migration: adding COPE fields to account_move")

    # List of fields to add: (column_name, column_type, default_value)
    fields_to_add = [
        ('import_export_cope', 'VARCHAR', None),
        ('nature_of_record', 'VARCHAR', None),
        ('value_type', 'VARCHAR', None),
        ('cope_account_type', 'VARCHAR', None),
        ('cope_country', 'INTEGER', None),
        ('cope_counterpart_country', 'INTEGER', None),
        ('cope_currency', 'INTEGER', None),
        ('cope_bank_identifier', 'INTEGER', None),
        ('cope_country_visible', 'BOOLEAN', 'FALSE'),
        ('cope_counterpart_visible', 'BOOLEAN', 'FALSE'),
    ]

    for column_name, column_type, default in fields_to_add:
        # Check if column exists
        cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='account_move'
            AND column_name=%s
        """, (column_name,))

        if not cr.fetchone():
            # Column doesn't exist, create it
            default_clause = f" DEFAULT {default}" if default else ""
            query = f"""
                ALTER TABLE account_move
                ADD COLUMN {column_name} {column_type}{default_clause}
            """
            _logger.info(f"Adding column: {column_name} ({column_type})")
            cr.execute(query)
        else:
            _logger.info(f"Column {column_name} already exists, skipping")

    _logger.info("Pre-migration completed: COPE fields added to account_move")