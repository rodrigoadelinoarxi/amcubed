import logging

from odoo import fields, models, _

_logger = logging.getLogger(__name__)

PAYMENT_CONFIRMATION_ACTIONS = [
    ('only_confirm_quotation', _('Only Confirm Quotation')),
    ('create_payment', _('Create Payment'))
]


class ProviderEuPago(models.Model):
    _inherit = 'payment.provider'

    eupago_secret_key = fields.Char(string='EuPago Secret Key')
    payment_confirmation_action = fields.Selection(PAYMENT_CONFIRMATION_ACTIONS, default='create_payment')
