import json
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Populate exemption_codes field for existing POS orders"""
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Find all POS orders without exemption_codes that have account moves with exemptions
    pos_orders = env['pos.order'].search([
        ('exemption_codes', '=', False),
        ('account_move', '!=', False)
    ])

    _logger.info(f"Updating exemption codes for {len(pos_orders)} POS orders")

    for order in pos_orders:
        try:
            exemption_codes = {}

            # Get exemption codes from the related account move
            if order.account_move and order.account_move.line_ids:
                for line in order.account_move.line_ids:
                    for tax in line.tax_ids:
                        if hasattr(tax, 'exemption_id') and tax.exemption_id:
                            exemption_codes[tax.exemption_id.id] = {
                                'code': tax.exemption_id.code,
                                'name': tax.exemption_id.name
                            }

            # If no exemption codes found in account move, try from original order lines
            if not exemption_codes:
                for line in order.lines:
                    for tax in line.tax_ids_after_fiscal_position:
                        if hasattr(tax, 'exemption_id') and tax.exemption_id:
                            exemption_codes[tax.exemption_id.id] = {
                                'code': tax.exemption_id.code,
                                'name': tax.exemption_id.name
                            }

            # Store exemption codes if found
            if exemption_codes:
                order.write({'exemption_codes': json.dumps(exemption_codes)})

        except Exception as e:
            _logger.error(f"Error updating exemption codes for POS order {order.id}: {e}")

    _logger.info("Exemption codes migration completed")