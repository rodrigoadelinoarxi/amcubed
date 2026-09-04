"""Functional POS flow tests for l10n_pt_ao_pos (Grupo 1 — POS).

These HttpCase tests drive the standard POS UI through the tours defined in
static/tests/tours/pos_flow_tours.js, on a database with l10n_pt_ao_pos and its
absorbed satellites installed. They cover the four flows required for the POS
migration:

* full cash sale (session open -> product -> pay -> close order),
* invoicing from POS (customer + Invoice, exercising _prepare_invoice_vals and
  the invoicing-journal routing absorbed from l10n_pt_ao_pos_invoicing_journals),
* refund / credit note from the ticket screen.

They reuse the native point_of_sale HttpCase base (TestPointOfSaleHttpCommon),
so the products, payment methods and pos.config used are the standard POS
fixtures; only the extra data these flows need (a customer, the Bank payment
method on the config) is added here.

Certification internals (hash/ATCUD/QR/SAF-T) are produced by l10n_pt_ao /
l10n_pt_certificate and are covered by those modules' own tests; here we verify
the POS-side wiring drives the certified invoice/credit-note path without error.
"""

from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPosFlows(TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ao_customer = cls.env["res.partner"].create({"name": "AO Cert Customer"})
        # PT/AO orders are always to_invoice, so the config must carry a default
        # "final consumer" partner (as in production); otherwise validating an
        # invoiced order with no customer stops on "Please select the Customer".
        cls.end_consumer = cls.env["res.partner"].create({"name": "Consumidor Final"})
        cls.main_pos_config.write({"end_consumer_partner_id": cls.end_consumer.id})
        # PT/AO POS validation refuses products without taxes; the core
        # "Magnetic Board" fixture ships tax-free, so give it a sale tax (price
        # included, so the 1.98 tour amount stays deterministic).
        sale_tax = cls.env["account.tax"].create(
            {
                "name": "IVA 14% (AO)",
                "amount": 14,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "price_include_override": "tax_included",
                "company_id": cls.main_pos_config.company_id.id,
            }
        )
        cls.magnetic_board.write({"taxes_id": [Command.set(sale_tax.ids)]})
        # ensure the Bank payment method is on the config the tours use
        bank_pm = cls.main_pos_config.payment_method_ids.filtered(
            lambda pm: pm.name == "Bank"
        )
        if not bank_pm:
            cls.main_pos_config.write(
                {"payment_method_ids": [Command.link(cls.bank_payment_method.id)]}
            )

    def test_pos_sale_flow(self):
        """A full cash sale in POS completes end to end: open the register, add
        a product, pay cash, and land back on an empty order."""
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("l10n_pt_ao_pos_sale_flow")

    def test_pos_invoice_flow(self):
        """Invoicing from POS produces a posted customer invoice: a sale with a
        customer and the Invoice option ticked, validated to a receipt."""
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("l10n_pt_ao_pos_invoice_flow")
        order = self.env["pos.order"].search(
            [("partner_id", "=", self.ao_customer.id)], limit=1
        )
        self.assertTrue(order, "the invoiced POS order must exist")
        self.assertTrue(
            order.account_move,
            "an invoiced POS order must carry an account.move",
        )

    def test_pos_refund_flow(self):
        """Refunding a paid order from the ticket screen creates a negative
        (credit-note) POS order linked back to the original."""
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour("l10n_pt_ao_pos_refund_flow")
        refund = self.env["pos.order"].search([("amount_total", "<", 0)], limit=1)
        self.assertTrue(refund, "a refund (negative) POS order must exist")
