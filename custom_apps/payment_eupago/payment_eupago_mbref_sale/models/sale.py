import logging

from odoo import api, fields, models, _
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from odoo.tools.float_utils import float_round
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    eu_pago_mbref = fields.Boolean()

    def create_mb_ref(self):
        tx = self.env['payment.transaction'].sudo().search([('sale_order_ids', 'in', self.ids)])
        if not tx:
            eupago_id = self.env['ir.sequence'].next_by_code('mbref.payment.number')
            provider = self.env['payment.provider'].search([
                ('code', '=', 'eupago_mbref'),
                ('company_id', '=', self.company_id.id)
            ])
            data_fim = date.today() + relativedelta(days=+provider.eupago_days_deadline)
            eupago_values = ({
                'chave'      : provider.eupago_secret_key,
                'valor'      : float_round(self.amount_to_invoice, 2),
                'id'         : eupago_id,
                'data_inicio': date.today().strftime('%Y-%m-%d'),
                'data_fim'   : data_fim.strftime('%Y-%m-%d')
            })
            vals = {
                'provider_id'      : provider.id,
                'sale_order_ids'   : [self.id],
                'amount'           : abs(self.amount_total),
                'currency_id'      : self.currency_id.id,
                'partner_id'       : self.partner_id.id,
                'payment_method_id': provider.payment_method_ids[0].id,
                'operation'        : 'online_redirect',
            }
            tx = self.env['payment.transaction'].create(vals)
            got_error, response = provider.eupago_mbref_validate_data(eupago_values, self.name)

            self.write({
                'transaction_ids': [(4, tx.id)]
            })
            tx.write({
                'reference'       : response['referencia'],
                'eupago_deadline' : datetime.now().date() + relativedelta(
                    days=+provider.eupago_days_deadline, hours=+23, minutes=+59, seconds=+59),
                'eupago_reference': response['referencia'],
                'eupago_entity'   : response['entidade'],
                'eupago_id'       : eupago_id,
            })

            self.message_post(body=Markup(_('<p>ATM Details  <br/> Entity: %s <br/> Reference: %s <br/> Amount: %s %s</p>'))
                                   % (response['entidade'],
                                      response['referencia'], tx.amount,
                                      self.currency_id.symbol))

    def action_quotation_send(self):
        if self.eu_pago_mbref:
            self.create_mb_ref()
        return super(SaleOrder, self).action_quotation_send()

    def action_quotation_sent(self):
        res = super(SaleOrder, self).action_quotation_sent()
        if self.eu_pago_mbref:
            self.create_mb_ref()
        return res

    def get_mb_ref_transaction(self):
        mb_ref = self.transaction_ids.filtered(lambda x: x.provider_code == 'eupago_mbref')
        return mb_ref and mb_ref[0]
