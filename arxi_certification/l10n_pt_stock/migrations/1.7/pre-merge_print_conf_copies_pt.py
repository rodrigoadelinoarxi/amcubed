# -*- coding: utf-8 -*-
"""Merge print_conf_copies_pt into l10n_pt_stock (v19).

Old databases have print_conf_copies_pt installed as a standalone (auto_install)
module that added the per-document print-copies configuration to stock.picking
and pt.transport, plus the copy-aware transport/delivery/picking reports. That
code now lives inside l10n_pt_stock, so this pre-migration:

1. Drops the inherited views/reports whose specs were merged into the existing
   l10n_pt_stock records (see OBSOLETE_VIEWS) — they must not be re-parented, or
   two records would fight over the same xpath.
2. Re-parents every remaining ir_model_data entry to l10n_pt_stock, keeping the
   record name; renames on collision as a safety net.
3. Marks the old module uninstalled WITHOUT running the uninstall routine (the
   print_copies data on stock.picking / pt.transport must survive).
4. Drops stale dependency rows so the upgrade does not fail on unmet dependency.

Idempotent: re-running finds nothing left to move.
"""
import logging

_logger = logging.getLogger(__name__)

MERGED_MODULES = ['print_conf_copies_pt']

NEW_MODULE = 'l10n_pt_stock'

# Inherited view/report records whose useful specs were merged into an existing
# l10n_pt_stock record — they must be dropped, not re-parented.
OBSOLETE_VIEWS = [
    ('print_conf_copies_pt', 'view_picking_form'),
    ('print_conf_copies_pt', 'pt_transport_view_form'),
    ('print_conf_copies_pt', 'report_transport'),
    ('print_conf_copies_pt', 'report_transport_document'),
    ('print_conf_copies_pt', 'report_deliveryslip'),
    ('print_conf_copies_pt', 'report_picking'),
]


def migrate(cr, version):
    """Re-parent the merged module's metadata into l10n_pt_stock.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on
        fresh installs, where there is nothing to merge)
    """
    if not version:
        return

    # 1. drop the inherited views/reports whose specs were merged into ours
    for module, name in OBSOLETE_VIEWS:
        cr.execute(
            """
            DELETE FROM ir_ui_view v
             USING ir_model_data d
             WHERE d.module = %s AND d.name = %s
               AND d.model = 'ir.ui.view' AND v.id = d.res_id
            """,
            (module, name),
        )
        if cr.rowcount:
            _logger.info('%s merge: dropped obsolete view %s.%s', NEW_MODULE, module, name)
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s AND model = 'ir.ui.view'",
            (module, name),
        )

    for old_module in MERGED_MODULES:
        # 2a. rename-on-collision (safety net)
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = %s,
                   name = d.name || '_' || d.module
             WHERE d.module = %s
               AND EXISTS (SELECT 1 FROM ir_model_data d2
                            WHERE d2.module = %s
                              AND d2.name = d.name)
            """,
            (NEW_MODULE, old_module, NEW_MODULE),
        )
        renamed = cr.rowcount
        # 2b. plain re-parent for everything else
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = %s
             WHERE d.module = %s
               AND NOT EXISTS (SELECT 1 FROM ir_model_data d2
                                WHERE d2.module = %s
                                  AND d2.name = d.name)
            """,
            (NEW_MODULE, old_module, NEW_MODULE),
        )
        moved = cr.rowcount
        # 2c. anything still left is an exact duplicate — drop only the metadata
        cr.execute("DELETE FROM ir_model_data WHERE module = %s", (old_module,))
        dropped = cr.rowcount

        # 3. mark the old module as gone without triggering an uninstall
        cr.execute(
            """
            UPDATE ir_module_module
               SET state = 'uninstalled', latest_version = NULL
             WHERE name = %s
               AND state NOT IN ('uninstalled', 'uninstallable')
            """,
            (old_module,),
        )

        # 4. stale dependency rows of modules that used to depend on it
        cr.execute("DELETE FROM ir_module_module_dependency WHERE name = %s", (old_module,))

        _logger.info(
            '%s merge: %s -> moved %s xml_ids (%s renamed, %s duplicates dropped)',
            NEW_MODULE, old_module, moved, renamed, dropped,
        )