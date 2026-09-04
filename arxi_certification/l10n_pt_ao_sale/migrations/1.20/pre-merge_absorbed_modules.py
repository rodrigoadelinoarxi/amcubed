# -*- coding: utf-8 -*-
"""Merge the absorbed satellite modules into l10n_pt_ao_sale (migração v19).

Old databases have these modules installed as standalone apps. Their code now
lives inside l10n_pt_ao_sale, so this pre-migration:

0. Deletes the satellites' inherited views whose xpath specs were merged
   directly into the core view files of l10n_pt_ao_sale (see OBSOLETE_VIEWS).
   Leaving them would duplicate UI elements — the "Print Configurations" group
   would show up twice on the sale order form.
1. Re-parents every remaining ir_model_data entry to l10n_pt_ao_sale, keeping
   the record ``name`` — it matches the xml_ids of the templates moved into the
   core files. On a name collision the record is renamed to
   ``<name>_<old_module>`` (safety net).
2. Marks the old modules as uninstalled WITHOUT running the uninstall routine —
   the templates must survive, they are now owned by l10n_pt_ao_sale. A real
   uninstall would drop the inherited views and silently disable both the
   per-country report mechanism and the print-copies loop.
3. Drops stale dependency rows so the upgrade does not fail on
   "unmet dependency" (l10n_pt_ao_sale used to depend on both).

Absorbed from ``sale_report_by_country``: the ``_get_name_sale_report()`` hook
and the ``report_saleorder`` template that calls it.
Absorbed from ``print_conf_copies_sales``: the ``print.conf.mixer`` inheritance
on sale.order plus the three report templates that render one copy per
``print_copies`` (Original/Duplicate/...).

Their report templates are NOT deleted (unlike OBSOLETE_VIEWS): they are
standalone inherited views kept as-is in the new module, with their original
xml_ids and priorities. Only the form view, whose xpath was merged into the
existing ``l10n_pt_ao_sale.view_order_form`` record, is dropped.

**Priority matters**: ``report_saleorder_raw`` (prio 10) must keep running
before ``report_saleorder`` (prio 16) — the first builds the copies loop around
the t-call, the second then swaps that t-call for the per-country template.

Idempotent: re-running finds nothing left to move.
"""
import logging

_logger = logging.getLogger(__name__)

MERGED_MODULES = ['sale_report_by_country', 'print_conf_copies_sales']

NEW_MODULE = 'l10n_pt_ao_sale'

# (module, xml_id name) of inherited views whose specs were merged into an
# existing l10n_pt_ao_sale view record — they must be dropped, not re-parented.
OBSOLETE_VIEWS = [
    ('print_conf_copies_sales', 'view_order_form_print_conf_copies'),
]


def migrate(cr, version):
    """Re-parent the merged modules' metadata into l10n_pt_ao_sale.

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
