import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EuPagoController(http.Controller):

    # Rota Callback registada na página EuPago para confirmarem o pagamento
    @http.route('/payment/eupago/notify', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def eupago_notify(self, **kwargs):
        transaction = \
            request.env['payment.transaction'].sudo().search([('eupago_id', '=', kwargs.get('identificador'))], limit=1)
        if kwargs.get('chave_api') == transaction.provider_id.eupago_secret_key:
            transaction._eupago_form_validate(kwargs)
        return ''  # we got an warning without a return (just saw that in paypal model)
