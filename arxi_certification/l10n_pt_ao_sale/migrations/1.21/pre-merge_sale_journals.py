# -*- coding: utf-8 -*-
"""Merge the absorbed ``sale_journals`` module into l10n_pt_ao_sale (migração v19).

Old databases have ``sale_journals`` installed as a standalone app. It OWNS two
models (``sale.order.type``, ``sale.order.journal``), six ``noupdate="1"`` sale
type records, a security group, plus views, menus and server actions — all of
which now live inside l10n_pt_ao_sale. This pre-migration:

0. Drops the two inherited views whose xpath specs were merged directly into
   existing l10n_pt_ao_sale records (see OBSOLETE_VIEWS): ``view_order_form``
   (journal/type fields + layout groups) and ``report_saleorder_document``
   (force document type name in the title). Leaving them would apply the same
   xpaths twice — duplicated fields on the form and a duplicated title override.
1. Re-parents every remaining ``ir_model_data`` entry to l10n_pt_ao_sale,
   keeping the record ``name`` — it matches the xml_ids of the models, data,
   groups, menus and actions moved into the new module (t_proforma, t_other,
   sale_order_journal_view_form, other_doc_menu, action_view_proforma, ...).
   On a name collision the record is renamed to ``<name>_<old_module>``.
2. Marks ``sale_journals`` uninstalled WITHOUT running the uninstall routine —
   the model tables (sale.order.type, sale.order.journal) and all their data
   rows (the journals created per company, the six sale types) must survive:
   they are now owned by l10n_pt_ao_sale. A real uninstall would DROP the
   tables and every journal/type record, destroying certified numbering.
3. Drops stale dependency rows so the upgrade does not fail on
   "unmet dependency" (l10n_pt_ao_sale, l10n_pt_ao_consignment_invoices and
   l10n_pt_ao_inactive_journals used to depend on sale_journals).

The models' data records (journals, types) are NOT touched beyond re-parenting
their metadata: the underlying rows in sale_order_journal / sale_order_type are
kept intact, so existing sale orders keep their journal and sequence.

Idempotent: re-running finds nothing left to move.
"""
import logging

_logger = logging.getLogger(__name__)

OLD_MODULE = 'sale_journals'
NEW_MODULE = 'l10n_pt_ao_sale'

# Inherited views whose specs were merged into an existing l10n_pt_ao_sale
# record — they must be dropped, not re-parented (else the xpaths apply twice).
OBSOLETE_VIEWS = [
    ('sale_journals', 'view_order_form'),
    ('sale_journals', 'report_saleorder_document'),
]


def migrate(cr, version):
    """Re-parent sale_journals' metadata into l10n_pt_ao_sale.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on
        fresh installs, where sale_journals was never present)
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
        (NEW_MODULE, OLD_MODULE, NEW_MODULE),
    )
    renamed = cr.rowcount
    # 1b. plain re-parent for everything else (models, data, group, menus, actions)
    cr.execute(
        """
        UPDATE ir_model_data d
           SET module = %s
         WHERE d.module = %s
           AND NOT EXISTS (SELECT 1 FROM ir_model_data d2
                            WHERE d2.module = %s
                              AND d2.name = d.name)
        """,
        (NEW_MODULE, OLD_MODULE, NEW_MODULE),
    )
    moved = cr.rowcount
    # 1c. anything still left is an exact duplicate of a core record —
    # drop only the metadata entry, never the referenced record
    cr.execute("DELETE FROM ir_model_data WHERE module = %s", (OLD_MODULE,))
    dropped = cr.rowcount

    # 2. mark sale_journals as gone WITHOUT triggering an uninstall (would drop
    #    the sale.order.type / sale.order.journal tables and their data)
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled', latest_version = NULL
         WHERE name = %s
           AND state NOT IN ('uninstalled', 'uninstallable')
        """,
        (OLD_MODULE,),
    )

    # 3. stale dependency rows of modules that used to depend on it
    cr.execute("DELETE FROM ir_module_module_dependency WHERE name = %s", (OLD_MODULE,))

    _logger.info(
        '%s merge: %s -> moved %s xml_ids (%s renamed, %s duplicates dropped)',
        NEW_MODULE, OLD_MODULE, moved, renamed, dropped,
    )