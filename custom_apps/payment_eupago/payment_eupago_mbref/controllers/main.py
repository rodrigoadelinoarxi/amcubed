import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EuPagoController(http.Controller):

    # Vai mostrar os dados returnados pela api
    @http.route('/payment/eupago/multibanco', type='http', website=True, auth="public")
    def show_multibanco_result(self, **post):
        if not post:
            return ''
        tx = request.env['payment.transaction'].sudo().search([('eupago_reference', '=', post.get('referencia'))])
        values = {
            'entidade'  : post.get('entidade'),
            'referencia': post.get('referencia'),
            'valor'     : str(round(float(post.get('valor')), 2)) + " " + request.env.user.currency_id.name,
            'enddate'   : tx.sudo().eupago_deadline.date()
        }
        return request.render("payment_eupago_mbref.eupago_multibanco_form", values)
