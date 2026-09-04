import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    This migration script populates the `invoicing_journal_id` field
    on existing `l10n_pt.account.series` records for invoicing documents.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    series_to_update = env['l10n_pt.account.series'].search([
        ('state', '=', 'active'),
        ('line_ids', '!=', False),
        ('document_type_category', '=', 'invoicing')
    ])

    _logger.info(f"Found {len(series_to_update)} active invoicing series with lines to migrate.")

    for series in series_to_update:
        first_line = series.line_ids[0]
        if not first_line.res_model or not first_line.res_id:
            _logger.warning(f"Series {series.code} (ID: {series.id}) has a line with no related record. Skipping.")
            continue

        related_record = env[first_line.res_model].browse(first_line.res_id)
        if not hasattr(related_record, 'journal_id'):
            _logger.warning(f"Series {series.code} (ID: {series.id}) has a related record "
                            f"of type {first_line.res_model} with no journal_id. Skipping.")
            continue

        journal = related_record.journal_id
        if series.invoicing_journal_id != journal:
            series.invoicing_journal_id = journal.id
            _logger.info(f"Updated invoicing journal for series {series.code} (ID: {series.id}) "
                         f"to {journal.name} (ID: {journal.id}).")