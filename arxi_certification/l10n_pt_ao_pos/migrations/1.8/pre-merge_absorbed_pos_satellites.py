# -*- coding: utf-8 -*-
"""Merge the absorbed thin POS satellite modules into l10n_pt_ao_pos.

Old databases have these modules installed as standalone (auto_install) apps.
Their code now lives inside l10n_pt_ao_pos, so this pre-migration re-parents
their metadata into the core POS module, following the same pattern as
l10n_pt_ao/migrations/1.37/pre-merge_absorbed_modules.py.

For each merged module it:
1. Re-parents every ir_model_data entry (views, fields, model metadata) from the
   old module to l10n_pt_ao_pos, keeping the record `name` (which matches the
   xml_ids of the files moved into the core). On a name collision with an
   existing l10n_pt_ao_pos entry, the record is renamed to ``<name>_<old_module>``.
2. Marks the old module as uninstalled WITHOUT running the uninstall routine —
   the data (e.g. pos.config.end_consumer_partner_id) must survive; it is now
   owned by l10n_pt_ao_pos.
3. Drops stale dependency rows pointing at the merged module so the upgrade of
   the remaining modules does not fail on "unmet dependency".

Idempotent: re-running finds nothing left to move.

Fusão POS, Grupo 1. Only the non-sensitive satellites are absorbed here;
l10n_pt_ao_pos_document_type (FS/FT/FR/NC — certification) is intentionally
NOT in this list and stays a standalone module for now.
"""
import logging

_logger = logging.getLogger(__name__)

MERGED_MODULES = [
    "l10n_pt_ao_pos_default_end_consumer",
    "l10n_pt_ao_pos_invoicing_journals",
    "l10n_pt_ao_pos_credit_note_reason",
]

# Inherited views whose specs were merged INTO the core view files — these
# records must be DELETED in old databases (their xml_ids are now provided by
# l10n_pt_ao_pos), otherwise they survive as orphan inherits duplicating the UI.
OBSOLETE_VIEWS = [
    ("l10n_pt_ao_pos_default_end_consumer", "pos_config_view_form"),
    # invoicing_journals: its res_config_settings_view_form (xml-id identical to
    # the core one) was merged into l10n_pt_ao_pos's own settings view.
    ("l10n_pt_ao_pos_invoicing_journals", "res_config_settings_view_form"),
]


def migrate(cr, version):
    """Re-parent the merged POS satellites' metadata into l10n_pt_ao_pos.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on fresh
        installs, where there is nothing to merge)
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
            _logger.info(
                "l10n_pt_ao_pos merge: dropped obsolete view %s.%s", module, name
            )
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s AND model = 'ir.ui.view'",
            (module, name),
        )

    for old_module in MERGED_MODULES:
        # 1a. rename-on-collision, matching the renames done in the moved XML
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
