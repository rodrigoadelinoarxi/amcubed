# -*- coding: utf-8 -*-
"""Merge stock_restrictions and stock_report_by_country into l10n_pt_stock (v19).

Old databases have both modules installed as standalone apps that l10n_pt_stock
depended on. Their code (a handful of stock.picking fields/methods and a return
wizard) now lives inside l10n_pt_stock, so this pre-migration:

0. Drops the stock_restrictions inherited form view whose useful xpaths were
   merged into l10n_pt_stock.view_picking_form (see OBSOLETE_VIEWS). Its dead
   xpaths (sale-only fields absent from stock.picking) were not carried over.
1. Re-parents every remaining ir_model_data entry (the absorbed fields
   is_editable / is_return and the report hook) to l10n_pt_stock, keeping the
   record name; renames on collision as a safety net.
2. Marks both old modules uninstalled WITHOUT running the uninstall routine —
   the fields must survive on stock.picking (is_return drives the certified
   transport document type; a real uninstall would drop the columns).
3. Drops stale dependency rows so the upgrade does not fail on
   "unmet dependency" (l10n_pt_stock used to depend on both).

Idempotent: re-running finds nothing left to move.
"""
import logging

_logger = logging.getLogger(__name__)

MERGED_MODULES = ['stock_restrictions', 'stock_report_by_country']

NEW_MODULE = 'l10n_pt_stock'

# Inherited views whose useful specs were merged into an existing l10n_pt_stock
# view record — they must be dropped, not re-parented.
OBSOLETE_VIEWS = [
    ('stock_restrictions', 'view_picking_form'),
]


def migrate(cr, version):
    """Re-parent the merged modules' metadata into l10n_pt_stock.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on
        fresh installs, where there is nothing to merge)
    """
    if not version:
        return

    # 0. drop the inherited views whose specs were merged into the core views
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
        # 1a. rename-on-collision (safety net)
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
        # 1b. plain re-parent for everything else
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
        # 1c. anything still left is an exact duplicate of a core record —
        # drop only the metadata entry, never the referenced record
        cr.execute("DELETE FROM ir_model_data WHERE module = %s", (old_module,))
        dropped = cr.rowcount

        # 2. mark the old module as gone without triggering an uninstall
        cr.execute(
            """
            UPDATE ir_module_module
               SET state = 'uninstalled', latest_version = NULL
             WHERE name = %s
               AND state NOT IN ('uninstalled', 'uninstallable')
            """,
            (old_module,),
        )

        # 3. stale dependency rows of modules that used to depend on it
        cr.execute("DELETE FROM ir_module_module_dependency WHERE name = %s", (old_module,))

        _logger.info(
            '%s merge: %s -> moved %s xml_ids (%s renamed, %s duplicates dropped)',
            NEW_MODULE, old_module, moved, renamed, dropped,
        )