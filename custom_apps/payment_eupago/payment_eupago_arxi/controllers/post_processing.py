import logging

from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EuPagoPaymentPostProcessing(PaymentPostProcessing):

    @http.route()
    def poll_status(self, **_kwargs):
        """ Fetch the transaction to display on the status page and finalize its post-processing.

        :return: The post-processing values of the transaction.
        :rtype: dict
        """
        # Retrieve the last user's transaction from the session.
        monitored_tx = request.env['payment.transaction'].sudo().browse(
            self.get_monitored_transaction_id()
        ).exists()
        if not monitored_tx:  # The session might have expired, or the tx has never existed.
            raise Exception('tx_not_found')
        if monitored_tx.provider_id.code != 'eupago_mbway':
            return super().poll_status(**_kwargs)

        # Return the post-processing values to display the transaction summary to the customer.
        return monitored_tx._get_post_processing_values()
