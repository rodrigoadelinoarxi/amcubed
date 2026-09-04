# -*- coding: utf-8 -*-
"""Merge the absorbed l10n_pt_edi_partner_filter module into l10n_pt_saphety.

Old databases have it installed as a standalone module. Its live code (partner
EDI preference fields + partner view) now lives inside l10n_pt_saphety, so
this pre-migration re-parents its ir_model_data (same record names), marks it
uninstalled WITHOUT running the uninstall (the partner field values must
survive) and drops stale dependency rows.

The account.edi.format override it carried (_get_move_applicability /
_get_pt_edi_export_method) was dead code serving only the cius_pt format of
the removed l10n_pt_edi module — dropped, nothing to migrate.

Idempotent: re-running finds nothing left to move.
"""
import logging

_logger = logging.getLogger(__name__)

MERGED_MODULES = [
    'l10n_pt_edi_partner_filter',
]


def migrate(cr, version):
    """Re-parent the merged module's metadata into l10n_pt_saphety.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on
        fresh installs, where there is nothing to merge)
    """
    if not version:
        return

    for old_module in MERGED_MODULES:
        # 1a. rename-on-collision (safety net; no known case)
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = 'l10n_pt_saphety',
                   name = d.name || '_' || d.module
             WHERE d.module = %s
               AND EXISTS (SELECT 1 FROM ir_model_data d2
                            WHERE d2.module = 'l10n_pt_saphety'
                              AND d2.name = d.name)
            """,
            (old_module,),
        )
        renamed = cr.rowcount
        # 1b. plain re-parent for everything else
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = 'l10n_pt_saphety'
             WHERE d.module = %s
               AND NOT EXISTS (SELECT 1 FROM ir_model_data d2
                                WHERE d2.module = 'l10n_pt_saphety'
                                  AND d2.name = d.name)
            """,
            (old_module,),
        )
        moved = cr.rowcount
        # 1c. exact duplicates: drop only the metadata entry, never the record
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
            'l10n_pt_saphety merge: %s -> moved %s xml_ids (%s renamed, %s duplicates dropped)',
            old_module, moved, renamed, dropped,
        )
