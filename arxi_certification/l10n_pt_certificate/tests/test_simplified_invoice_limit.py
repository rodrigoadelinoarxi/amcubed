from odoo import Command, fields

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


class TestSimplifiedInvoiceLimit(AccountTestPTInvoicingCommon):
    """CIVA Art. 40: a simplified invoice (FS) is normally capped at 100€.
    A retailer/street vendor selling goods (never services) to the final
    consumer may raise that cap to 1000€ — but only when every condition
    holds; any single one missing falls back to the 100€ limit.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_type_fs = cls.env["account.document.type"].search(
            [
                ("code", "=", "FS"),
                ("country_id", "=", cls.env.ref("base.pt").id),
                ("is_refund", "=", False),
            ],
            limit=1,
        )
        cls.final_consumer = cls.env.ref("l10n_pt_certificate.final_consumer")
        # A self-paid document (FS/FR) auto-creates its payment on posting,
        # which requires a *certified* cash/bank journal. payment_journal_id
        # is a compute field (falls back to the company's first bank/cash
        # journal) — rather than race it with a new journal, certify the
        # ones generic_coa already created.
        cls.env["account.journal"].search(
            [
                ("company_id", "=", cls.company.id),
                ("type", "in", ("bank", "cash")),
            ]
        ).l10n_cert = True
        cls.goods_product = cls.env["product.product"].create(
            {
                "name": "Goods Test Product",
                "default_code": "GOODS001",
                "type": "consu",
                "lst_price": 900.0,
                "taxes_id": [Command.set(cls.tax_sale.ids)],
            }
        )

    def _create_fs_invoice(self, partner, product, price_unit):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": self.sale_journal.id,
                "document_type_id": self.document_type_fs.id,
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "quantity": 1.0,
                            "price_unit": price_unit,
                            "tax_ids": [Command.set(self.tax_sale.ids)],
                        }
                    )
                ],
            }
        )

    def test_general_limit_blocks_over_100(self):
        """Baseline (non-retailer company): FS over 100€ is blocked."""
        invoice = self._create_fs_invoice(self.partner, self.goods_product, 150.0)
        with self.assertRaises(Exception):
            invoice.action_post()

    def test_general_limit_allows_up_to_100(self):
        """Baseline: FS at/under 100€ posts fine, regardless of product type
        or customer, when the company isn't a registered retailer. (80€ net
        + 23% IVA = 98.4€ total, under the 100€ limit.)"""
        invoice = self._create_fs_invoice(self.partner, self.goods_product, 80.0)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_retailer_flag_alone_does_not_raise_the_limit(self):
        """Being a retailer isn't enough on its own — the customer must also
        be the final consumer and the line must be goods, not services."""
        self.company.l10n_pt_retailer_or_street_vendor = True
        invoice = self._create_fs_invoice(self.partner, self.goods_product, 150.0)
        with self.assertRaises(Exception):
            invoice.action_post()

    def test_retailer_goods_final_consumer_allows_up_to_1000(self):
        """All three conditions met: retailer, goods only, final consumer —
        the 1000€ limit applies. (700€ net + 23% IVA = 861€ total, over the
        general 100€ limit but under the 1000€ retail one.)"""
        self.company.l10n_pt_retailer_or_street_vendor = True
        invoice = self._create_fs_invoice(self.final_consumer, self.goods_product, 700.0)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_retailer_goods_final_consumer_still_blocks_over_1000(self):
        """Even for a qualifying retail sale, 1000€ is a hard cap too."""
        self.company.l10n_pt_retailer_or_street_vendor = True
        invoice = self._create_fs_invoice(self.final_consumer, self.goods_product, 1500.0)
        with self.assertRaises(Exception):
            invoice.action_post()

    def test_retailer_service_line_falls_back_to_100(self):
        """A service line disqualifies the retail exception even for a
        retailer selling to the final consumer."""
        self.company.l10n_pt_retailer_or_street_vendor = True
        invoice = self._create_fs_invoice(self.final_consumer, self.product, 150.0)
        with self.assertRaises(Exception):
            invoice.action_post()

    def test_retailer_business_customer_falls_back_to_100(self):
        """A non-final-consumer customer disqualifies the retail exception
        even for a retailer selling goods."""
        self.company.l10n_pt_retailer_or_street_vendor = True
        invoice = self._create_fs_invoice(self.partner, self.goods_product, 150.0)
        with self.assertRaises(Exception):
            invoice.action_post()
