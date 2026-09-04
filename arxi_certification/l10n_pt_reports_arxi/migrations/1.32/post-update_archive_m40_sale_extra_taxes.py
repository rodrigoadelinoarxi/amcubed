import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    imd_records = env["ir.model.data"].search([
        ("model", "=", "account.tax"),
        ("name", "ilike", "m40_sale_extra"),
    ])

    taxes = env["account.tax"].browse(imd_records.mapped("res_id")).exists()
    taxes_to_archive = taxes.filtered("active")
    taxes_to_archive.write({"active": False})

    _logger.info(
        "Archived %s tax(es) with external id containing 'm40_sale_extra' (%s external id record(s) matched)",
        len(taxes_to_archive),
        len(imd_records),
    )
