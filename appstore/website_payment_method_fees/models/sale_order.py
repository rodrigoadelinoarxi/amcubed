# -*- coding: utf-8 -*-

from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _remove_extra_fees_line(self):
        if self.state == 'draft':
            extra_fees_line = self.order_line.filtered(lambda line: line.is_extra_fees)
            if extra_fees_line:
                extra_fees_line.sudo().unlink()

    def _manage_extra_fees_line(self, transaction):
        self._remove_extra_fees_line()
        fees_product_id = transaction.payment_method_id.fees_service_id
        if transaction.payment_method_id.fees_active and fees_product_id and transaction.payment_method_id.fees_percent > 0:
            extra_fees = transaction.payment_method_id._compute_fees(transaction.amount)
            if extra_fees:
                self.env['sale.order.line'].create({
                    'product_id': fees_product_id.id,
                    'product_uom_qty': 1,
                    'order_id': self.id,
                    'price_unit': extra_fees,
                    'is_extra_fees': True
                })


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_extra_fees = fields.Boolean('Is Extra Fees')

    def _show_in_cart(self):
        return not self.is_extra_fees and super()._show_in_cart()
