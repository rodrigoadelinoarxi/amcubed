"""Remove the obsolete account.journal view left behind in the database.

O campo `l10n_pt_cope_exclude` foi retirado do modulo, mas a vista que o usava
continua em bases de dados antigas. Como e irma de outras vistas que herdam
`account.view_account_journal_form`, o Odoo revalida-a ao carregar qualquer uma
delas e falha com:

    ParseError: O campo "l10n_pt_cope_exclude" nao existe no modelo "account.journal"
"""

import logging

_logger = logging.getLogger(__name__)

OBSOLETE_VIEWS = [
    ("l10n_pt_reports_arxi", "view_account_journal_form_l10n_pt_reports_arxi"),
]


def migrate(cr, version):
    if not version:
        return

    for module, name in OBSOLETE_VIEWS:
        # A vista tem de ser removida com TODA a sua descendencia: um DELETE
        # directo viola `ir_ui_view_inherit_id_fkey` se outra vista a herdar.
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
            _logger.info(
                "l10n_pt_reports_arxi: removed %s obsolete view(s) for %s.%s (and descendants)",
                cr.rowcount, module, name,
            )
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s AND model = 'ir.ui.view'",
            (module, name),
        )
