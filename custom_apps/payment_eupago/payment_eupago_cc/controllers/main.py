import logging
from datetime import datetime

from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EuPagoController(http.Controller):

    # Vai mostrar os dados returnados pela api
    @http.route('/eupago_status=ok', type='http', website=True, auth="public")
    def show_eupagostatus_ok(self, **post):
        return request.redirect("/my/home")

    @http.route('/payment/eupago/cc/request', type='json', auth="public")
    def request_cc(self, **post):
        if not post:
            return ''
        tx = request.env['payment.transaction'].sudo().search([('reference', 'ilike', post['reference'])], limit=1)
        eupago_id = request.env['ir.sequence'].sudo().next_by_code('cc.payment.number')
        eupago_values = {
            'payment' : {
                'identifier': eupago_id,
                'amount'    : {
                    'value'   : tx.amount,
                    'currency': 'EUR'
                },
                'failUrl'   : request.env['ir.config_parameter'].sudo().get_param('web.base.url') + "/shop/payment",
                'successUrl': request.env['ir.config_parameter'].sudo().get_param('web.base.url') + "/payment/status",
                'backUrl'   : request.env['ir.config_parameter'].sudo().get_param('web.base.url') + "/shop/payment",
                'lang'      : 'PT'
            },
            'customer': {
                'email' : post.get('email'),
                'notify': True
            }
        }
        got_error, response = tx.provider_id.eupago_cc_validate_data(eupago_values, post.get('reference'))
        if got_error:
            raise ValidationError(got_error)
        tx.sudo().write({
            'reference'       : response['reference'],
            'eupago_reference': response['reference'],
            'eupago_id'       : eupago_id,
            'eupago_deadline' : datetime.now() + relativedelta(minutes=+15)
        })
        tx.sudo()._set_pending()
        return response
