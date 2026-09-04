import json
import logging

import requests

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class ProviderEuPago(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('eupago_cc', 'euPago CC')],
                            ondelete={'eupago_cc': 'set default'})
    eupago_credit_card_minimum_amount = fields.Float(string='Credit Card Minimum Amount', default=1)
    eupago_credit_card_reserve_days = fields.Integer(string='Reservation days', default=6)

    def _eupago_cc_get_api_url(self):
        """ Return the API URL according to the state.

        Note: self.ensure_one()

        :return: The API URL
        :rtype: str
        """
        self.ensure_one()
        if self.state == 'enabled':
            return 'https://clientes.eupago.pt/api/v1.02/creditcard/create'
        else:
            return 'https://sandbox.eupago.pt/api/v1.02/creditcard/create'

    def eupago_cc_get_form_action_url(self):
        """
        Returns the internal route path that shows the result of the payment transaction after communication
        :return: url
        """
        base = self.get_base_url()
        return str(base + "/payment/eupago/cc/request")

    def eupago_cc_validate_data(self, eupago_values, tx_ref, max_try=50):
        """
        Method to perform the communication with EuPago with webservices
        Validates that the amount is valid based on the configuration
        Tries to create the Mbref on EuPago backend and returns either the payload or an error message
        """
        tx = self.env['payment.transaction'].sudo().search([('reference', '=', tx_ref)])
        api_url = self._eupago_cc_get_api_url()
        headers = {
            "Accept"       : "application/json",
            "Content-Type" : "application/json",
            "Authorization": "ApiKey " + self.eupago_secret_key
        }
        json_data = json.dumps(eupago_values)
        for i in range(max_try):
            try:
                json_response = requests.post(api_url, json=eupago_values, headers=headers)
                response = json.loads(json_response.content)
                if response['transactionStatus'] == 'Success':
                    return [False, response]
                elif response['transactionStatus'] == 'Rejected':
                    tx.sudo()._set_error(response['text'])
                    return [_("Service down. Please try again later."), False]
            except Exception as err:
                _logger.warning("URL Call Error. %d/%d. URL: %s" % (i, max_try, err.__str__()))
        else:
            tx.sudo()._set_error(_('Service down'))
            return [_("Service down. Please try again later."), False]
