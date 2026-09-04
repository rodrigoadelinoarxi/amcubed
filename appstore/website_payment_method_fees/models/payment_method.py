# -*- coding: utf-8 -*-

from odoo import models, fields, api,_
from odoo.exceptions import ValidationError

class PaymentMethod(models.Model):
    _inherit = 'payment.method'

    fees_active = fields.Boolean(string="Add Extra Fees")
    fees_percent = fields.Float(string="Fees Percent")
    fees_service_id = fields.Many2one('product.product', string="Fees Product", ondelete="restrict")

    @api.constrains('fees_active', 'fees_percent')
    def _constrains_fees(self):
        for method in self:
            if method.fees_active and not (0 <= method.fees_percent <= 100):
                raise ValidationError(_('Not valid amount for fees percent'))

    def _compute_fees(self, amount):
        self.ensure_one()
        fees = 0.0
        if self.fees_active:
            fees = amount * (self.fees_percent/100)
            taxes = self.fees_service_id.taxes_id.filtered(lambda tax: tax.company_id == self.env.company)
            if taxes:
                fees = taxes.compute_all(fees, product=self.fees_service_id)['total_included']
        return fees


