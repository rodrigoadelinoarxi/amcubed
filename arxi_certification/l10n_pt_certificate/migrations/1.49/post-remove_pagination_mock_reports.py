import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Replaced by the measured-pagination probe (report_invoice_document_probe/
# report_invoice_probe/account_invoices_probe) — the empirical mock-render
# pipeline these XML IDs used to belong to no longer exists in the module's
# data files. Removing a <record>/<template> from a data file does not
# delete it from the database on module update, so an upgrade from an
# older version leaves these orphaned without this migration.
REMOVED_XMLIDS = [
    "l10n_pt_certificate.report_invoice_document_mock",
    "l10n_pt_certificate.report_invoice_mock",
    "l10n_pt_certificate.account_invoices_mock",
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in REMOVED_XMLIDS:
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            record.unlink()
            _logger.info("l10n_pt_certificate: removed orphaned %s", xmlid)
