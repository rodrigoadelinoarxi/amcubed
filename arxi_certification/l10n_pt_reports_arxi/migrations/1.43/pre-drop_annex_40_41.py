import logging

_logger = logging.getLogger(__name__)

MODULE = 'l10n_pt_reports_arxi'
REPORT_XMLIDS = ['tax_report_pt_anexo_40', 'tax_report_pt_anexo_41']


def migrate(cr, version):
    """Delete the annex 40/41 reports and their metadata before the update.

    :param cr: database cursor
    :param version: installed version before the upgrade (None on fresh install,
        where the reports do not exist yet)
    """
    if not version:
        return

    for xmlid in REPORT_XMLIDS:
        cr.execute(
            "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s AND model = 'account.report'",
            (MODULE, xmlid),
        )
        row = cr.fetchone()
        if not row:
            continue
        report_id = row[0]

        cr.execute("DELETE FROM account_report WHERE id = %s", (report_id,))

        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s AND model = 'account.report'",
            (MODULE, xmlid),
        )
        _logger.info('%s: dropped report %s (id %s) for clean recreation', MODULE, xmlid, report_id)

    cr.execute(
        """
        DELETE FROM ir_model_data d
         WHERE d.module = %s
           AND d.model = 'account.report.line'
           AND NOT EXISTS (SELECT 1 FROM account_report_line l WHERE l.id = d.res_id)
        """,
        (MODULE,),
    )
    cr.execute(
        """
        DELETE FROM ir_model_data d
         WHERE d.module = %s
           AND d.model = 'account.report.expression'
           AND NOT EXISTS (SELECT 1 FROM account_report_expression e WHERE e.id = d.res_id)
        """,
        (MODULE,),
    )