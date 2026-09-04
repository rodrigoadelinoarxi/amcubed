import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Disable the native "Self-service invoicing" portal QR
    (point_of_sale_use_ticket_qr_code) on existing companies.

    The post_init_hook only runs on a fresh install; a migrated client updates
    (-u) the already-installed module, so this migration turns the setting off
    for them too. PT/AO receipts already carry the legally-required AT QR code
    (l10n_pt_pos); the portal QR would print a second, non-legal QR.
    """
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].search(
        [("point_of_sale_use_ticket_qr_code", "=", True)]
    )
    if companies:
        companies.write({"point_of_sale_use_ticket_qr_code": False})
        _logger.info(
            "Disabled Self-service invoicing portal QR on %s companies",
            len(companies),
        )
