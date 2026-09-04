"""
Pre-migration script to remove view_move_form_inherit_l10n_reports.

This script removes the old view to avoid conflicts during module upgrade.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove the view_move_form_inherit_l10n_reports view."""
    _logger.info("Starting pre-migration: removing view_move_form_inherit_l10n_reports")

    # Check if the view exists
    cr.execute("""
        SELECT res_id
        FROM ir_model_data
        WHERE module = 'l10n_pt_reports_arxi'
        AND name = 'view_move_form_inherit_l10n_reports'
        AND model = 'ir.ui.view'
    """)

    view_data = cr.fetchone()

    if not view_data:
        _logger.info("View view_move_form_inherit_l10n_reports does not exist, skipping removal")
        return

    # Delete the view record
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT res_id
            FROM ir_model_data
            WHERE module = 'l10n_pt_reports_arxi'
            AND name = 'view_move_form_inherit_l10n_reports'
            AND model = 'ir.ui.view'
        )
    """)

    deleted_views = cr.rowcount
    _logger.info(f"Deleted {deleted_views} view record(s)")

    # Delete the ir_model_data record
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'l10n_pt_reports_arxi'
        AND name = 'view_move_form_inherit_l10n_reports'
        AND model = 'ir.ui.view'
    """)

    deleted_data = cr.rowcount
    _logger.info(f"Deleted {deleted_data} ir_model_data record(s)")

    _logger.info("Pre-migration completed: view_move_form_inherit_l10n_reports removed")
