import json
import logging

import requests

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProviderEuPago(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('eupago_mbway', 'euPago MBWay')],
                            ondelete={'eupago_mbway': 'set default'})
    eupago_mbway_minimum_amount = fields.Float(string='MBWay Minimum Amount', default=0.50)

    def _eupago_mbway_get_api_url(self):
        """ Return the API URL according to the state.

        Note: self.ensure_one()

        :return: The API URL
        :rtype: str
        """
        self.ensure_one()
        if self.state == 'enabled':
            return 'https://clientes.eupago.pt/clientes/rest_api/mbway/create'
        else:
            return 'https://sandbox.eupago.pt/clientes/rest_api/mbway/create'

    def eupago_mbway_get_form_action_url(self):
        """
        Returns the internal route path that shows the result of the payment transaction after communication
        :return: url
        """
        base = self.get_base_url()
        return str(base + "/payment/eupago/multibanco")

    def eupago_mbway_validate_data(self, eupago_values, tx_ref, max_try=50):
        """
        Method to perform the communication with EuPago with webservices
        Validates that the amount is valid based on the configuration
        Tries to create the Mbref on EuPago backend and returns either the payload or an error message
        """
        tx = self.env['payment.transaction'].sudo().search([('reference', '=', tx_ref)])
        if tx.amount < self.eupago_mbway_minimum_amount:
            raise UserError(_('Invalid amount! %s is the minimum amount.') % str(
                self.eupago_mbway_minimum_amount) + self.env.user.currency_id.name)

        if not eupago_values['alias'].isdigit() or len(eupago_values['alias']) != 9:
            raise UserError(_('Invalid reference! Please provide a valid nine digit reference.'))

        api_url = self._eupago_mbway_get_api_url()
        for i in range(max_try):
            try:
                json_data = json.dumps(eupago_values)
                json_response = requests.post(api_url, json_data)
                response = json.loads(json_response.content)
                if response['estado'] == 0:
                    return [False, response]
                elif response['estado'] in (-8, -9, -10, -11):
                    tx.sudo()._set_error(response['resposta'])
                    return [_("Service down. Please try again later."), False]
                elif response['estado'] == -7:
                    _logger.info(_('Error Eupago: Service down'))  # Debug
            except Exception as err:
                _logger.warning("URL Call Error. %d/%d. URL: %s" % (i, max_try, err.__str__()))
        else:
            tx.sudo()._set_error(_('Service down'))
            return [_("Service down. Please try again later."), False]
