import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    eupago_reference = fields.Char(string="EuPago Reference")
    eupago_entity = fields.Char(string="EuPago Entity")
