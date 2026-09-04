import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EuPagoController(http.Controller):

    # Vai enviar a info para a API
    @http.route('/payment/eupago/mbway/request', type='json', auth="public")
    def request_mbway(self, **post):
        if not post:
            return ''
        tx = request.env['payment.transaction'].sudo().search([('reference', 'ilike', post['reference'])], limit=1)
        eupago_id = request.env['ir.sequence'].sudo().next_by_code('mbway.payment.number')
        eupago_values = ({
            'chave': tx.provider_id.eupago_secret_key,
            'valor': tx.amount,
            'id'   : eupago_id,
            'alias': post.get('alias')
        })
        got_error, response = tx.provider_id.eupago_mbway_validate_data(eupago_values, post.get('reference'))
        tx.sudo().write({
            'reference'       : response['referencia'],
            'eupago_reference': response['referencia'],
            'eupago_id'       : eupago_id,
            'eupago_deadline' : datetime.now() + relativedelta(minutes=+15)
        })
        tx.sudo()._set_pending()
