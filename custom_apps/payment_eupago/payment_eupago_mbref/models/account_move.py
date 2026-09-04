import logging

from odoo import api, fields, models, _
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from odoo.tools.float_utils import float_round
from markupsafe import Markup

_logger = logging.getLogger(__name__)
class AccountMove(models.Model):
    _inherit = 'account.move'

    eu_pago_mbref = fields.Boolean()

    def action_create_mb_ref(self):
        eupago_id = self.env['ir.sequence'].next_by_code('mbref.payment.number')
        provider = self.env['payment.provider'].search([
            ('code', '=', 'eupago_mbref'),
            ('company_id', '=', self.company_id.id)
        ])
        data_fim = date.today() + relativedelta(days=+provider.eupago_days_deadline)
        eupago_values = ({
            'chave'      : provider.eupago_secret_key,
            'valor'      : float_round(self.amount_residual, 2),
            'id'         : eupago_id,
            'data_inicio': date.today().strftime('%Y-%m-%d'),
            'data_fim'   : data_fim.strftime('%Y-%m-%d')
        })
        vals = {
            'provider_id'      : provider.id,
            'invoice_ids'   : [self.id],
            'amount'           : abs(self.amount_residual),
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
        tx._set_pending()

        self.message_post(body=Markup(_('<p>ATM Details  <br/> Entity: %s <br/> Reference: %s <br/> Amount: %s %s</p>'))
                               % (response['entidade'],
                                  response['referencia'], tx.amount,
                                  self.currency_id.symbol))
        self.eu_pago_mbref = True
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'views': [[self.env.ref('account.view_move_form').id, 'form']],
                'res_id': self.id,
                'target': 'main',
            }
    def action_post(self):
        res = super(AccountMove, self).action_post()
        for rec in self:
            if rec.state == 'posted' and rec.eu_pago_mbref:
                rec.action_create_mb_ref()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        moves = super(AccountMove, self).create(vals_list)
        for rec in moves:
            if rec.move_type == 'out_refund':
                rec.eu_pago_mbref = False

        return moves