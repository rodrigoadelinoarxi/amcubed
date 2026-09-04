# -*- coding: utf-8 -*-
"""Merge the absorbed l10n_pt_arxi_coa module into l10n_pt_certificate.

Old databases have l10n_pt_arxi_coa installed as a standalone module. Its code
(chart template pt_arxi, tax report, report line extensions) now lives inside
l10n_pt_certificate, so this pre-migration:

1. Re-parents every ir_model_data entry (tax report + report lines ``trp_*``,
   groups, model/field metadata) from l10n_pt_arxi_coa to l10n_pt_certificate,
   keeping the record names — they match the xml_ids of the moved files, and
   l10n_pt_reports_arxi now references them as ``l10n_pt_certificate.*``.
   On a name collision with an existing entry, the record is renamed to
   ``<name>_l10n_pt_arxi_coa`` (safety net; no known case).
2. Marks l10n_pt_arxi_coa as uninstalled WITHOUT running the uninstall
   routine — the data must survive, it is now owned by l10n_pt_certificate.
3. Drops stale dependency rows pointing at the merged module.

The per-company chart-of-accounts records created from the pt_arxi template
live under ``module='account'`` xml_ids (Odoo 17+ convention) and are not
touched; the template CSVs are simply discovered in this module from now on.

Idempotent: re-running finds nothing left to move.
"""
import logging

_logger = logging.getLogger(__name__)

MERGED_MODULES = [
    'l10n_pt_arxi_coa',
]

# Modules removed for good (Etapa 1/2.2 da migração v19): flagged 'to remove'
# so Odoo runs a real uninstall during the upgrade (EDI formats, views and
# fields cleaned up). Signed PDFs/XMLs live in ir.attachment records attached
# to the documents and are NOT owned by these modules — they survive.
REMOVED_MODULES = [
    'l10n_pt_edi',
    'l10n_pt_multicert',
]


def migrate(cr, version):
    """Re-parent the merged module's metadata into l10n_pt_certificate.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on
        fresh installs, where there is nothing to merge)
    """
    if not version:
        return

    # 0. flag the removed modules for a REAL uninstall (data cleanup)
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'to remove'
         WHERE name IN %s
           AND state = 'installed'
        """,
        (tuple(REMOVED_MODULES),),
    )
    if cr.rowcount:
        _logger.info('l10n_pt_certificate cleanup: %s removed module(s) flagged for uninstall', cr.rowcount)

    for old_module in MERGED_MODULES:
        # 1a. rename-on-collision (safety net)
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = 'l10n_pt_certificate',
                   name = d.name || '_' || d.module
             WHERE d.module = %s
               AND EXISTS (SELECT 1 FROM ir_model_data d2
                            WHERE d2.module = 'l10n_pt_certificate'
                              AND d2.name = d.name)
            """,
            (old_module,),
        )
        renamed = cr.rowcount
        # 1b. plain re-parent for everything else
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = 'l10n_pt_certificate'
             WHERE d.module = %s
               AND NOT EXISTS (SELECT 1 FROM ir_model_data d2
                                WHERE d2.module = 'l10n_pt_certificate'
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
            'l10n_pt_certificate merge: %s -> moved %s xml_ids (%s renamed, %s duplicates dropped)',
            old_module, moved, renamed, dropped,
        )
