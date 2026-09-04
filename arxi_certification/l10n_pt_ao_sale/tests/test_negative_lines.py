"""Negative quantity/price/total rules on certified sale order lines.

Pins the 2026-08-20 cleanup: ``sale.order.line._check_non_negative_values``
must forbid negative *quantity* only (a negative document total is a
separate check in ``validate_order()``); negative *unit price* stays
allowed, since it's the only way to register a manual discount line.
Before that cleanup, the constrain also blocked negative unit price,
contradicting that decision.

``sale.order.journal.l10n_pt_ao_certified`` only turns True via the
``l10n_pt_cert`` field, which is added by ``l10n_pt_sale`` — a different,
optional repo (``l10n_pt``) not among this module's dependencies. Rather
than pull in that cross-repo dependency just for tests, the compute is
patched here to force a "certified" journal locally.
"""

from odoo import Command
from odoo.addons.l10n_pt_ao.tests.test_l10n_pt_ao_common import (
    AccountTestCertifiedCommon,
)
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSaleOrderNegativeLines(AccountTestCertifiedCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        sequence = cls.env["ir.sequence"].search(
            [("code", "=", "sale.order")], limit=1
        )
        sale_type = cls.env["sale.order.type"].search([], limit=1)
        cls.sale_order_journal = cls.env["sale.order.journal"].create(
            {
                "name": "Certified Sale Orders",
                "sequence_id": sequence.id,
                "sale_type_id": sale_type.id,
                "company_id": cls.company.id,
            }
        )

    def setUp(self):
        super().setUp()

        def _force_certified(recs):
            for rec in recs:
                rec.l10n_pt_ao_certified = True

        self.patch(
            type(self.env["sale.order.journal"]),
            "is_sale_journal_l10n_pt_ao_certified",
            _force_certified,
        )
        self.sale_order_journal.invalidate_recordset(["l10n_pt_ao_certified"])

    def _create_order(self, quantity=1.0, price_unit=None):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sale_journal": self.sale_order_journal.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": quantity,
                            "price_unit": (
                                price_unit
                                if price_unit is not None
                                else self.product.lst_price
                            ),
                        }
                    ),
                ],
            }
        )

    def test_negative_quantity_forbidden_on_certified_order(self):
        """Negative quantity on a certified sale order line is blocked."""
        with self.assertRaises(ValidationError):
            self._create_order(quantity=-1.0)

    def test_negative_unit_price_allowed_on_certified_order(self):
        """Negative unit price alone (e.g. a manual discount line) is
        allowed — only quantity and the order total are restricted."""
        order = self._create_order(quantity=2.0, price_unit=-10.0)
        self.assertEqual(order.order_line.price_unit, -10.0)

    def test_negative_total_forbidden_on_order_validation(self):
        """A certified sale order whose total goes negative is blocked at
        ``validate_order()``, even though the negative unit price that
        caused it is, by itself, allowed on the line."""
        order = self._create_order(quantity=1.0, price_unit=-50.0)

        with self.assertRaises(ValidationError):
            order.validate_order()

    def test_negative_quantity_forbidden_even_on_discount_product(self):
        """UAT 15b follow-up (2026-08-26): the discount product used to be
        exempt from this rule — leftover from when it also covered
        negative *price* (removed 2026-08-20). A discount is a negative
        *price* on a positive-quantity line; it never needs a negative
        quantity, so it's not special-cased any more."""
        self.company.sale_discount_product_id = self.product
        with self.assertRaises(ValidationError):
            self._create_order(quantity=-1.0)

    def test_negative_quantity_forbidden_even_on_downpayment_product(self):
        """Same as above for the down payment product — native Odoo always
        creates down-payment lines with quantity 1.0
        (``sale/wizard/sale_make_invoice_advance.py``), so there's no
        legitimate case for a negative quantity there either."""
        self.company.sale_downpayment_product_id = self.product
        with self.assertRaises(ValidationError):
            self._create_order(quantity=-1.0)
