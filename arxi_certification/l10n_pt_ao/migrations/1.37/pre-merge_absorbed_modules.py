# -*- coding: utf-8 -*-
"""Merge the absorbed satellite modules into l10n_pt_ao (Bloco C, migração v19).

Old databases have these modules installed as standalone apps. Their code now
lives inside l10n_pt_ao, so this pre-migration:

0. Deletes the satellites' inherited views/templates whose xpath specs were
   merged directly into the core view files (decisão do técnico: as vistas são
   absorvidas nas existentes, sem manter inherits paralelos) — see
   OBSOLETE_VIEWS. Leaving them would duplicate UI elements.
1. Re-parents every remaining ir_model_data entry (standalone views, menus,
   actions, access rules, config parameters, model/field metadata) from the
   old module to l10n_pt_ao — keeping the record `name`, which matches the
   xml_ids of the files moved into the core. On a name collision with an
   existing l10n_pt_ao entry, the record is renamed to ``<name>_<old_module>``
   (safety net; no known case after the view merge).
2. Marks the old module as uninstalled WITHOUT running the uninstall routine —
   the data must survive, it is now owned by l10n_pt_ao.
3. Drops stale dependency rows pointing at the merged modules so the upgrade
   of the remaining modules does not fail on "unmet dependency".

Idempotent: re-running finds nothing left to move.

Note: ir.config_parameter KEYS keep their historical names
(``automatic_refs.*``) on purpose — they are plain strings read by the core
code and renaming them would need a data migration with no benefit.
"""
import logging

_logger = logging.getLogger(__name__)

MERGED_MODULES = [
    'automatic_refs',
    'tax_exemptions',
    'invoice_shipping_info',
    'print_conf_copies',
    'restrict_update_company_info',
    'account_cancel_reason',
    'credit_note_reason',
    # replaced by the core protected-report mechanism (Bloco D), not merged:
    # its enforcement now lives in ir_actions_report.py/ir_ui_view.py
    'studio_protected_reports',
]

# Modules removed for good (Etapa 1 da migração v19) — unlike the merged ones
# their data must NOT survive. Their code is gone from the repo, so Odoo's own
# uninstall can never run (it would have to import the module): _force_uninstall()
# does the whole cleanup in SQL right here instead.
# contract_instance_checker is NOT here: it moved to the arxi-quality repo
# keeping the same module name, so installed DBs keep it running from the new
# location. Same reasoning for sale_force_invoiced: it is upstream OCA
# (ForgeFlow, sale-workflow) and was only being vendored here — dropping it from
# this repo does not uninstall it, so DBs that use it keep their force_invoiced
# data and serve the module from the OCA repo instead.
REMOVED_MODULES = [
    'sh_message',
    'sh_import_journal_entry',
    'credit_note_smart_button',
    'ir_rule_protected',
    'access_apps',
    'access_restricted',
    'restricted_settings',
]

# Models replaced by the unified account.move.reason: their registry metadata
# is removed (the code no longer defines them); the TABLE is kept untouched as
# a data safeguard — post-unify_move_reasons.py copies its rows.
DROPPED_MODELS = [
    'account.move.refund.reason',
]

# Window actions/menu entries pointing at dropped models — deleted instead of
# re-parented (they would stay broken).
OBSOLETE_ACTIONS = [
    ('credit_note_reason', 'account_move_refund_reason_action'),
]

# Inherited views/templates whose specs were merged INTO the core view files —
# these records must be DELETED in old databases (their xml_ids no longer
# exist), otherwise they would survive as orphan inherits duplicating the UI
# elements now provided by the core views.
OBSOLETE_VIEWS = [
    ('automatic_refs', 'res_config_settings_view_form'),
    ('automatic_refs', 'view_partner_form_automatic_ref'),
    ('invoice_shipping_info', 'view_move_form'),
    ('invoice_shipping_info', 'report_invoice_document'),
    ('print_conf_copies', 'view_company_form_print_conf_copies'),
    ('print_conf_copies', 'view_partner_form_print_conf_copies'),
    ('print_conf_copies', 'invoice_form_print_conf_copies'),
    ('print_conf_copies', 'view_account_payment_form_print_conf_copies'),
    ('print_conf_copies', 'print_copies_report_invoice'),
    ('print_conf_copies', 'print_copies_report_invoice_document'),
    ('print_conf_copies', 'report_payment_receipt_document'),
    ('account_cancel_reason', 'view_move_form'),
    ('account_cancel_reason', 'view_account_payment_form'),
    ('account_cancel_reason', 'report_invoice_account_cancel_reason'),
    ('account_cancel_reason', 'report_payment_inherit'),
    ('credit_note_reason', 'view_account_move_reversal'),
    ('credit_note_reason', 'account_move_refund_reason_view_tree'),
    ('credit_note_reason', 'account_move_refund_reason_view_search'),
]


def migrate(cr, version):
    """Re-parent the merged modules' metadata into l10n_pt_ao.

    :param cr: database cursor
    :param version: installed module version before the upgrade (None on
        fresh installs, where there is nothing to merge)
    """
    if not version:
        return

    # 0. drop the inherited views whose specs were merged into the core views
    #
    # A vista tem de ser removida com TODA a sua descendencia: um DELETE directo
    # viola `ir_ui_view_inherit_id_fkey` sempre que exista outra vista a herda-la
    # (acontece com dados reais de producao, nao no ambiente local).
    for module, name in OBSOLETE_VIEWS:
        cr.execute(
            """
            WITH RECURSIVE target AS (
                SELECT v.id
                  FROM ir_ui_view v
                  JOIN ir_model_data d
                    ON d.model = 'ir.ui.view' AND d.res_id = v.id
                 WHERE d.module = %s AND d.name = %s
                UNION ALL
                SELECT child.id
                  FROM ir_ui_view child
                  JOIN target t ON child.inherit_id = t.id
            )
            DELETE FROM ir_ui_view WHERE id IN (SELECT id FROM target)
            """,
            (module, name),
        )
        if cr.rowcount:
            _logger.info('l10n_pt_ao merge: dropped obsolete view %s.%s', module, name)
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s AND model = 'ir.ui.view'",
            (module, name),
        )

    # 0a-bis. uninstall the removed modules HERE, in SQL.
    #
    # ``state = 'to remove'`` is NOT enough: the real uninstall runs inside
    # load_modules(), which has to IMPORT the module to call its uninstall
    # hooks. These modules were deleted from the repo, so that import can never
    # succeed and they stay stuck in 'to remove' forever — resurfacing on every
    # later upgrade as "Some modules have inconsistent states".
    for module in REMOVED_MODULES:
        _force_uninstall(cr, module)

    # 0b. drop window actions pointing at dropped models
    for module, name in OBSOLETE_ACTIONS:
        cr.execute(
            """
            DELETE FROM ir_act_window a
             USING ir_model_data d
             WHERE d.module = %s AND d.name = %s
               AND d.model = 'ir.actions.act_window' AND a.id = d.res_id
            """,
            (module, name),
        )
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s",
            (module, name),
        )

    # 0c. remove registry metadata of dropped models (tables stay as safeguard)
    for model in DROPPED_MODELS:
        cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE (model = 'ir.model' AND res_id IN (SELECT id FROM ir_model WHERE model = %s))
                OR (model = 'ir.model.fields' AND res_id IN (SELECT id FROM ir_model_fields WHERE model = %s))
                OR (model = 'ir.model.fields.selection' AND res_id IN (
                        SELECT s.id FROM ir_model_fields_selection s
                        JOIN ir_model_fields f ON s.field_id = f.id WHERE f.model = %s))
            """,
            (model, model, model),
        )
        cr.execute(
            "DELETE FROM ir_model_fields_selection WHERE field_id IN (SELECT id FROM ir_model_fields WHERE model = %s)",
            (model,),
        )
        cr.execute("DELETE FROM ir_model_fields WHERE model = %s", (model,))
        cr.execute("DELETE FROM ir_model WHERE model = %s", (model,))
        _logger.info('l10n_pt_ao merge: dropped registry metadata of %s (table kept)', model)

    for old_module in MERGED_MODULES:
        # 1a. rename-on-collision, matching the renames done in the moved XML
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = 'l10n_pt_ao',
                   name = d.name || '_' || d.module
             WHERE d.module = %s
               AND EXISTS (SELECT 1 FROM ir_model_data d2
                            WHERE d2.module = 'l10n_pt_ao'
                              AND d2.name = d.name)
            """,
            (old_module,),
        )
        renamed = cr.rowcount
        # 1b. plain re-parent for everything else
        cr.execute(
            """
            UPDATE ir_model_data d
               SET module = 'l10n_pt_ao'
             WHERE d.module = %s
               AND NOT EXISTS (SELECT 1 FROM ir_model_data d2
                                WHERE d2.module = 'l10n_pt_ao'
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
        cr.execute("DELETE FROM ir_module_module_dependency WHERE name = %s", (old_module,))

        _logger.info(
            'l10n_pt_ao merge: %s -> moved %s xml_ids (%s renamed, %s duplicates dropped)',
            old_module, moved, renamed, dropped,
        )


def _force_uninstall(cr, module):
    """Remove every trace of `module` in SQL, without loading its Python code.

    Reproduces what Odoo's own uninstall would do, for modules whose code no
    longer exists on disk. Deletion order follows the foreign keys: UI records
    first, then the schema, then the registry metadata, ir_model_data last.
    """
    cr.execute("SELECT state FROM ir_module_module WHERE name = %s", (module,))
    row = cr.fetchone()
    if not row or row[0] in ('uninstalled', 'uninstallable'):
        return

    # 1. menus, children before parents (parent_id has no ON DELETE CASCADE)
    cr.execute(
        """
        WITH RECURSIVE owned AS (
            SELECT res_id AS id FROM ir_model_data
             WHERE module = %s AND model = 'ir.ui.menu'
        ), tree AS (
            SELECT m.id FROM ir_ui_menu m JOIN owned o ON o.id = m.id
            UNION
            SELECT c.id FROM ir_ui_menu c JOIN tree t ON c.parent_id = t.id
        )
        DELETE FROM ir_ui_menu WHERE id IN (SELECT id FROM tree)
        """,
        (module,),
    )

    # 2. views, same reasoning as OBSOLETE_VIEWS above: a view inheriting one
    #    of ours would be left with a dangling inherit_id
    cr.execute(
        """
        WITH RECURSIVE owned AS (
            SELECT res_id AS id FROM ir_model_data
             WHERE module = %s AND model = 'ir.ui.view'
        ), tree AS (
            SELECT v.id FROM ir_ui_view v JOIN owned o ON o.id = v.id
            UNION
            SELECT c.id FROM ir_ui_view c JOIN tree t ON c.inherit_id = t.id
        )
        DELETE FROM ir_ui_view WHERE id IN (SELECT id FROM tree)
        """,
        (module,),
    )

    # 3. actions, record rules and access rights
    for table, imd_model in (
        ('ir_act_window', 'ir.actions.act_window'),
        ('ir_act_server', 'ir.actions.server'),
        ('ir_act_report_xml', 'ir.actions.report'),
        ('ir_rule', 'ir.rule'),
        ('ir_model_access', 'ir.model.access'),
    ):
        cr.execute(
            "DELETE FROM " + table + " WHERE id IN ("
            " SELECT res_id FROM ir_model_data WHERE module = %s AND model = %s)",
            (module, imd_model),
        )

    # 4. models owned EXCLUSIVELY by this module -> their tables can go.
    #    A model also claimed by other modules is a core model this one merely
    #    extended (ir.rule, res.users, ir.module.module): dropping its ir_model
    #    row would wreck the database.
    cr.execute(
        """
        SELECT m.id, m.model FROM ir_model m
         WHERE m.id IN (SELECT res_id FROM ir_model_data
                         WHERE module = %s AND model = 'ir.model')
           AND NOT EXISTS (SELECT 1 FROM ir_model_data d2
                            WHERE d2.model = 'ir.model' AND d2.res_id = m.id
                              AND d2.module != %s)
        """,
        (module, module),
    )
    own_models = cr.fetchall()
    own_ids = tuple(m[0] for m in own_models)
    for dummy_id, model_name in own_models:
        cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % model_name.replace('.', '_'))
        _logger.info('force uninstall %s: dropped table of %s', module, model_name)

    # 5. columns this module added to models it does not own
    cr.execute(
        """
        SELECT f.model, f.name FROM ir_model_fields f
         WHERE f.id IN (SELECT res_id FROM ir_model_data
                         WHERE module = %s AND model = 'ir.model.fields')
           AND f.store AND f.ttype NOT IN ('many2many', 'one2many')
           AND (%s OR f.model_id NOT IN %s)
        """,
        (module, not own_ids, own_ids or (0,)),
    )
    for model_name, field_name in cr.fetchall():
        cr.execute(
            'ALTER TABLE IF EXISTS "%s" DROP COLUMN IF EXISTS "%s" CASCADE'
            % (model_name.replace('.', '_'), field_name)
        )

    # 6. registry metadata. ir_model_relation/ir_model_constraint are not
    #    cascaded from ir_model, so they have to go first.
    if own_ids:
        cr.execute("DELETE FROM ir_model_relation WHERE model IN %s", (own_ids,))
        cr.execute("DELETE FROM ir_model_constraint WHERE model IN %s", (own_ids,))
    cr.execute(
        """
        DELETE FROM ir_model_fields_selection
         WHERE field_id IN (SELECT res_id FROM ir_model_data
                             WHERE module = %s AND model = 'ir.model.fields')
        """,
        (module,),
    )
    cr.execute(
        """
        DELETE FROM ir_model_fields
         WHERE id IN (SELECT res_id FROM ir_model_data
                       WHERE module = %s AND model = 'ir.model.fields')
        """,
        (module,),
    )
    if own_ids:
        cr.execute("DELETE FROM ir_model WHERE id IN %s", (own_ids,))

    # 7. xml_ids and module bookkeeping, both directions of the dependency graph
    cr.execute("DELETE FROM ir_model_data WHERE module = %s", (module,))
    cr.execute("DELETE FROM ir_module_module_dependency WHERE name = %s", (module,))
    cr.execute(
        """
        DELETE FROM ir_module_module_dependency
         WHERE module_id = (SELECT id FROM ir_module_module WHERE name = %s)
        """,
        (module,),
    )
    cr.execute(
        """
        UPDATE ir_module_module
           SET state = 'uninstalled', latest_version = NULL
         WHERE name = %s
        """,
        (module,),
    )
    _logger.info(
        'force uninstall %s: done (%s own model(s) dropped)', module, len(own_models),
    )
