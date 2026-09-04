"""Regression test (PQC 2026-08): PT/AO down payment invoices must use the
company's configured down payment product, on both the sale order's own
down payment line and the resulting invoice line.

Before this fix, the override doing this
(``sale.advance.payment.inv._prepare_down_payment_lines_values``) was dead
code — that wizard method doesn't exist in this Odoo version (it was
renamed/restructured: a down payment SO line is now built directly from a
tax-computed "base line" via ``sale.order
._prepare_down_payment_line_values_from_base_line``, not from a wizard-side
list of line dicts). The override never ran, so the SO's down payment line
stayed productless — native Odoo's own down payment lines are deliberately
without a product, which certified invoicing (SAF-T, tax code lookups) does
not tolerate.
"""
from odoo import Command
from odoo.addons.l10n_pt_ao.tests.test_l10n_pt_ao_common import (
    AccountTestCertifiedCommon,
)
from odoo.exceptions import RedirectWarning
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDownPaymentProduct(AccountTestCertifiedCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.downpayment_product = cls.env["product.product"].create(
            {
                "name": "Down Payment Test Product",
                "type": "service",
                "invoice_policy": "order",
            }
        )
        cls.company.sale_downpayment_product_id = cls.downpayment_product

    def _create_confirmed_order(self, price_unit=1000.0):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": price_unit,
                            "tax_ids": [Command.set(self.tax_sale.ids)],
                        }
                    ),
                ],
            }
        )
        order.action_confirm()
        return order

    def _create_downpayment_invoice(self, order, percentage=50.0):
        wizard = (
            self.env["sale.advance.payment.inv"]
            .with_context(active_model="sale.order", active_ids=order.ids)
            .create(
                {
                    "advance_payment_method": "percentage",
                    "amount": percentage,
                }
            )
        )
        wizard.create_invoices()
        return order.invoice_ids.filtered(lambda m: m.state == "draft") or order.invoice_ids[-1:]

    def test_downpayment_so_line_gets_company_product(self):
        """The sale order's own down payment line must carry the company's
        configured product, not the native productless placeholder."""
        order = self._create_confirmed_order()
        self._create_downpayment_invoice(order)

        downpayment_lines = order.order_line.filtered(
            lambda l: l.is_downpayment and not l.display_type
        )
        self.assertTrue(downpayment_lines)
        self.assertEqual(downpayment_lines.product_id, self.downpayment_product)

    def test_downpayment_invoice_line_gets_company_product_and_rounded_price(self):
        order = self._create_confirmed_order(price_unit=1000.0)
        invoice = self._create_downpayment_invoice(order, percentage=50.0)

        product_lines = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        self.assertTrue(product_lines)
        self.assertEqual(product_lines.product_id, self.downpayment_product)
        # 50% of 1000 (+ 23% tax) untaxed is 500.00 — must round to the
        # currency's decimal precision, not carry extra digits of
        # tax-computation precision through to the invoice line.
        currency = order.currency_id
        for line in product_lines:
            self.assertEqual(
                currency.round(line.price_unit),
                line.price_unit,
                "price_unit must already be rounded to currency precision",
            )

    def test_downpayment_without_configured_product_raises(self):
        self.company.sale_downpayment_product_id = False
        order = self._create_confirmed_order()
        with self.assertRaises(RedirectWarning):
            self._create_downpayment_invoice(order)
