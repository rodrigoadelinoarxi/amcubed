import logging

_logger = logging.getLogger(__name__)

# Vistas antigas a remover antes da actualizacao do modulo.
OLD_VIEWS = (
    "l10n_pt_ao_view_account_list",
    "report_custom_invoice_document",
    "view_account_form",
)


def _remove_view_fallback(cr, module, name):
    """Remove a vista e TODA a sua descendencia, de baixo para cima.

    Usado apenas quando `odoo.upgrade.util` nao esta disponivel.
    Um `DELETE` directo viola `ir_ui_view_inherit_id_fkey` sempre que exista
    uma vista a herdar a que se apaga (acontece com dados reais de producao).
    """
    cr.execute(
        """
        WITH RECURSIVE target AS (
            SELECT v.id
              FROM ir_ui_view v
              JOIN ir_model_data d
                ON d.model = 'ir.ui.view' AND d.res_id = v.id
             WHERE d.module = %s AND d.name = %s
            UNION ALL
            SELECT f.id
              FROM ir_ui_view f
              JOIN target t ON f.inherit_id = t.id
        )
        DELETE FROM ir_ui_view WHERE id IN (SELECT id FROM target)
        """,
        [module, name],
    )
    removed = cr.rowcount
    cr.execute(
        "DELETE FROM ir_model_data WHERE module = %s AND name = %s AND model = 'ir.ui.view'",
        [module, name],
    )
    return removed


def migrate(cr, version):
    """Remove vistas antigas do l10n_pt_ao antes da actualizacao.

    Usa `util.remove_view()` (oficial da Odoo), que apaga a vista e as vistas
    que dela herdam — incluindo copias COW de multi-website — e limpa as
    referencias em `t-call`. Sem isso, o DELETE rebenta com ForeignKeyViolation
    em bases de dados de producao onde existam vistas herdadas.
    """
    _logger.info("Running l10n_pt_ao pre-migration: removing old views")

    try:
        from odoo.upgrade import util
    except ImportError:
        util = None
        _logger.info("odoo.upgrade.util not available; falling back to local recursive removal")

    for name in OLD_VIEWS:
        xml_id = "l10n_pt_ao.%s" % name
        if util is not None:
            util.remove_view(cr, xml_id)
            _logger.info("Removed view %s (and descendants)", xml_id)
        else:
            removed = _remove_view_fallback(cr, "l10n_pt_ao", name)
            if removed:
                _logger.info("Removed %s view(s) for %s (and descendants)", removed, xml_id)

    _logger.info("Finished l10n_pt_ao pre-migration")
