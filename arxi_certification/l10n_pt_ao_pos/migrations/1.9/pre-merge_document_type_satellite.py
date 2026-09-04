# -*- coding: utf-8 -*-
"""Merge the l10n_pt_ao_pos_document_type satellite into l10n_pt_ao_pos.

document_type (FS/FT/FR/NC) is certification-sensitive, so it was intentionally
left out of the 1.8 merge. Its code (the pos.order.document_type field, the
_prepare_invoice_vals document-type routing, and the POS document-type buttons)
now lives inside l10n_pt_ao_pos, so this pre-migration re-parents its metadata
into the core POS module, following the same pattern as
1.8/pre-merge_absorbed_pos_satellites.py.

For the merged module it:
1. Re-parents every ir_model_data entry (the pos.order.document_type field, any
   view/model metadata) from the old module to l10n_pt_ao_pos, keeping the record
   ``name``. On a name collision the record is renamed to ``<name>_<old_module>``.
2. Marks the old module as uninstalled WITHOUT running the uninstall routine, so
   the pos.order.document_type column and its data survive; it is now owned by
   l10n_pt_ao_pos.
3. Drops stale dependency rows pointing at the merged module.

Idempotent: re-running finds nothing left to move.
"""
import logging

_logger = logging.getLogger(__name__)

MERGED_MODULES = [
    "l10n_pt_ao_pos_document_type",
]


def migrate(cr, version):
    """Re-parent the document_type satellite's metadata into l10n_pt_ao_pos.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on fresh
        installs, where there is nothing to merge)
    """
    if not version:
        return

    for old_module in MERGED_MODULES:
        # 1a. rename-on-collision
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = 'l10n_pt_ao_pos',
                   name = d.name || '_' || d.module
             WHERE d.module = %s
               AND EXISTS (SELECT 1 FROM ir_model_data d2
                            WHERE d2.module = 'l10n_pt_ao_pos'
                              AND d2.name = d.name)
            """,
            (old_module,),
        )
        renamed = cr.rowcount
        # 1b. plain re-parent for everything else
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = 'l10n_pt_ao_pos'
             WHERE d.module = %s
               AND NOT EXISTS (SELECT 1 FROM ir_model_data d2
                                WHERE d2.module = 'l10n_pt_ao_pos'
                                  AND d2.name = d.name)
            """,
            (old_module,),
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
        cr.execute(
            "DELETE FROM ir_module_module_dependency WHERE name = %s", (old_module,)
        )

        _logger.info(
            "l10n_pt_ao_pos merge: %s -> moved %s xml_ids (%s renamed, %s duplicates dropped)",
            old_module,
            moved,
            renamed,
            dropped,
        )
