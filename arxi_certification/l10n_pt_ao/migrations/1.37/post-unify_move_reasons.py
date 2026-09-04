# -*- coding: utf-8 -*-
"""Copy the legacy credit note reasons into the unified account.move.reason.

Runs AFTER the ORM created the account_move_reason table (post-migration).
The legacy ``account_move_refund_reason`` table is kept untouched as a data
safeguard (same policy as the pt_arxi_ column migrations); its registry
metadata was removed by pre-merge_absorbed_modules.py.

Idempotent: rows are only inserted when the unified table has no row with the
same name yet.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Insert legacy refund reasons as reason_type='refund' records.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on
        fresh installs, where there is nothing to copy)
    """
    if not version:
        return

    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'account_move_refund_reason'")
    if not cr.fetchone():
        return

    cr.execute(
        """
        INSERT INTO account_move_reason
               (sequence, name, reason_type, active,
                create_uid, create_date, write_uid, write_date)
        SELECT r.sequence, r.name, 'refund', TRUE,
               r.create_uid, r.create_date, r.write_uid, r.write_date
          FROM account_move_refund_reason r
         WHERE NOT EXISTS (
                   SELECT 1 FROM account_move_reason u WHERE u.name = r.name
               )
        """
    )
    _logger.info('l10n_pt_ao merge: copied %s refund reasons into account.move.reason', cr.rowcount)
