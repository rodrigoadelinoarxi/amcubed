import json
import logging

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('eupago_mbref', 'euPago MB Ref')],
                                ondelete={'eupago_mbref': 'set default'})
    eupago_days_deadline = fields.Integer(string='Validity days', default=30,
                                          help="Validity days (between 1 and 30)", required_if_provider='eupago')
    eupago_multibanco_minimum_amount = fields.Float(string='ATM Minimum Amount', default=1)

    @api.constrains('eupago_days_deadline')
    def _check_eupago_days_deadline(self):
        for rec in self:
            if not 0 <= rec.eupago_days_deadline <= 30:
                raise UserError(_('The number of validity days must be between 0 and 30'))

    def _eupago_mbref_get_api_url(self):
        """ Return the API URL according to the state.

        Note: self.ensure_one()

        :return: The API URL
        :rtype: str
        """
        self.ensure_one()
        if self.state == 'enabled':
            return 'https://clientes.eupago.pt/clientes/rest_api/multibanco/create'
        else:
            return 'https://sandbox.eupago.pt/clientes/rest_api/multibanco/create'

    def eupago_mbref_get_form_action_url(self):
        """
        Returns the internal route path that shows the result of the payment transaction after communication
        :return: url
        """
        base = self.get_base_url()
        return str(base + "/payment/eupago/multibanco")

    def eupago_mbref_validate_data(self, eupago_values, tx_ref, max_try=50):
        """
        Method to perform the communication with EuPago with webservices
        Validates that the amount is valid based on the configuration
        Tries to create the Mbref on EuPago backend and returns either the payload or an error message
        """
        tx = self.env['payment.transaction'].sudo().search([('reference', '=', tx_ref)])
        if tx.amount < self.eupago_multibanco_minimum_amount:
            raise UserError(_('Invalid amount! %s is the minimum amount.') % str(
                self.eupago_multibanco_minimum_amount) + self.env.user.currency_id.name)
        api_url = self._eupago_mbref_get_api_url()
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
