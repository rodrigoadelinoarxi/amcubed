import logging
from datetime import datetime

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class EupagoTransaction(models.Model):
    _inherit = 'payment.transaction'

    eupago_deadline = fields.Datetime(string='Deadline for Payment')
    eupago_id = fields.Char()

    def _eupago_check_deadline(self):
        """
        Checks date deadline and if it's already overdue, it cancels the transaction
        :return:
        """
        txs = self.env['payment.transaction'].sudo().search([('eupago_deadline', '<=', datetime.now()),
                                                             ('state', 'in', ['draft', 'pending'])])
        for tx in txs:
            _logger.info('EuPago: Cancel tx (ref %s)', self.reference)
            tx.write({
                'state'        : 'cancel',
                'state_message': _('Outdated transaction')
            })

    def _eupago_form_validate(self, data):
        """
        Confirms payment after calling the EuPago Webservice
        :param data: payload from EuPago Webservice
        :return:
        """
        if self.state not in ['draft', 'pending']:
            _logger.info('EuPago: trying to validate an already validated tx (ref %s)', self.reference)
            return True
        _logger.info('Validated EuPago payment for tx %s: set as done' % self.reference)
        self.sudo()._set_done()
        if self.provider_id.payment_confirmation_action == 'only_confirm_quotation':
            confirmed_orders = self._check_amount_and_confirm_order()
            confirmed_orders._send_order_confirmation_mail()
            (self.sale_order_ids - confirmed_orders)._send_payment_succeeded_for_order_mail()
        else:
            self.sudo().with_context(payment_transaction=True)._finalize_post_processing()
        return True
