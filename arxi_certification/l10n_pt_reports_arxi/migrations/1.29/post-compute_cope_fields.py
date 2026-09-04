"""
Post-migration script to populate COPE fields on recent account moves.

This script computes COPE fields only for moves from the current year
to avoid performance issues during upgrade. Older moves will remain
with NULL values unless manually updated.
"""

import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Compute COPE fields for account moves from current year."""
    from odoo import api, SUPERUSER_ID

    _logger.info("Starting post-migration: computing COPE fields")

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Get current year start date
    current_year = datetime.now().year
    date_from = f"{current_year}-01-01"

    _logger.info(f"Computing COPE fields for moves from {date_from} onwards")

    # Find moves from current year with payments (COPE relevant)
    # Process in batches to avoid memory issues
    batch_size = 500
    offset = 0

    # Get total count first
    cr.execute("""
        SELECT COUNT(DISTINCT am.id)
        FROM account_move am
        WHERE am.date >= %s
        AND EXISTS (
            SELECT 1
            FROM account_payment ap
            WHERE ap.move_id = am.id
        )
    """, (date_from,))
    total_count = cr.fetchone()[0]

    _logger.info(f"Found {total_count} moves to process")

    if total_count == 0:
        _logger.info("No moves to process, skipping")
        return

    processed = 0
    while True:
        # Fetch move IDs in batches
        cr.execute("""
            SELECT DISTINCT am.id
            FROM account_move am
            WHERE am.date >= %s
            AND EXISTS (
                SELECT 1
                FROM account_payment ap
                WHERE ap.move_id = am.id
            )
            ORDER BY am.id
            LIMIT %s OFFSET %s
        """, (date_from, batch_size, offset))

        move_ids = [row[0] for row in cr.fetchall()]

        if not move_ids:
            break

        # Process this batch
        moves = env['account.move'].browse(move_ids)

        _logger.info(f"Processing batch: {offset} to {offset + len(move_ids)} of {total_count}")

        try:
            # Trigger compute methods for this batch
            # The compute methods have dependencies, so we need to call them in order
            moves._compute_import_export_cope()
            moves._compute_value_type()
            moves._compute_nature_of_record()
            moves._compute_cope_account_type()
            moves._compute_cope_active_country()
            moves._compute_cope_currency()
            moves._compute_cope_bank_identifier()
            moves._compute_cope_country_visible()
            moves._compute_cope_counterpart_visible()

            processed += len(move_ids)
            _logger.info(f"Successfully processed {processed}/{total_count} moves")

        except Exception as e:
            _logger.error(f"Error processing batch starting at offset {offset}: {str(e)}")
            # Continue with next batch even if this one fails

        offset += batch_size

    _logger.info(f"Post-migration completed: {processed} moves processed")
    _logger.info("Older moves were not processed. They can be recomputed manually if needed.")