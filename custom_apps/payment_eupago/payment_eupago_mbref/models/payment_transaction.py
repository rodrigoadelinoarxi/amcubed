import logging
from datetime import datetime, date

from dateutil.relativedelta import relativedelta

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    eupago_reference = fields.Char(string="EuPago Reference")
    eupago_entity = fields.Char(string="EuPago Entity")

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Eupago MBRef-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of acquirer-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'eupago_mbref':
            return res
        eupago_id = self.env['ir.sequence'].next_by_code('mbref.payment.number')
        data_fim = date.today() + relativedelta(days=+self.provider_id.eupago_days_deadline)
        eupago_values = ({
            'chave'      : self.provider_id.eupago_secret_key,
            'valor'      : round(float(processing_values.get('amount')), 2),
            'id'         : eupago_id,
            'data_inicio': date.today().strftime('%Y-%m-%d'),
            'data_fim'   : data_fim.strftime('%Y-%m-%d')
        })
        got_error, response = self.provider_id.eupago_mbref_validate_data(eupago_values,
                                                                          processing_values.get('reference'))
        tx = self.env['payment.transaction'].sudo().search(
            [('reference', '=', processing_values.get('reference')),
             ('partner_id', '=', processing_values.get('partner_id')),
             ('state', '=', 'draft')], limit=1)
        tx.write({
            'reference'       : response['referencia'],
            'eupago_deadline' : datetime.now().date() + relativedelta(
                days=+self.provider_id.eupago_days_deadline, hours=+23, minutes=+59, seconds=+59),
            'eupago_reference': response['referencia'],
            'eupago_entity'   : response['entidade'],
            'eupago_id'       : eupago_id
        })
        tx._set_pending()
        return {
            'entidade'  : response['entidade'],
            'referencia': response['referencia'],
            'valor'     : eupago_values.get('valor'),
            'enddate'   : eupago_values.get('data_fim'),
            'api_url'   : self.provider_id.eupago_mbref_get_form_action_url(),
            'return_url': self.provider_id.eupago_mbref_get_form_action_url(),
        }
