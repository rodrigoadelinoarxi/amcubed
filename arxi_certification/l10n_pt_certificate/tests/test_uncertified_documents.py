from odoo import Command, fields
from odoo.tests import tagged

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


@tagged("post_install", "-at_install")
class TestUncertifiedDocuments(AccountTestPTInvoicingCommon):
    """Non-certified (l10n_cert=False) journals must never get AT-specific
    fields. The general "uncertified behaves like stock Odoo" rules
    (negative lines, missing references, locking, credit-note origin) are
    tested in ``l10n_pt_ao`` — this module only adds the hash/ATCUD fields
    on top of certified documents, so it only needs to pin their absence
    here."""

    def test_posting_does_not_assign_hash_or_atcud(self):
        """An uncertified invoice posts without any certification hash/ATCUD."""
        move = self._create_invoice(self.uncertified_sale_journal)
        move.action_post()

        self.assertEqual(move.state, "posted")
        self.assertFalse(move.pt_arxi_inalterable_hash)
        self.assertFalse(move.pt_arxi_atcud)

    def test_ordinary_vendor_bill_posts_like_native_odoo(self):
        """A vendor bill received from an external supplier (``source_billing
        == 'I'``, the correct setting for a purchase journal that isn't
        self-billing) must post exactly like standard Odoo.

        Regression test for an operator-precedence bug in ``_post()``'s
        ``pt_invs`` filter (``r.country_code == "PT" and (r.is_sale_document()
        and r.journal_id.l10n_cert) or r.is_purchase_document()``): due to
        Python's ``and``/``or`` precedence, the missing parentheses meant
        *any* ``is_purchase_document()`` — regardless of country or
        self-billing — was routed through the certified-document pipeline,
        including ``_pt_arxi_check_certified_import`` (which has no
        sale/purchase or self-billing guard of its own and raises unless
        ``journal_id.source_billing == 'P'``), incorrectly blocking normal
        vendor bill posting on any purchase journal correctly configured as
        an external/integrated source.
        """
        purchase_journal = self.env["account.journal"].create(
            {
                "name": "Vendor Bills",
                "type": "purchase",
                "code": "VBILL",
                "company_id": self.company.id,
                "source_billing": "I",
            }
        )
        vendor = self.env["res.partner"].create(
            {"name": "External Vendor", "country_id": self.env.ref("base.pt").id}
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "journal_id": purchase_journal.id,
                "partner_id": vendor.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            # self.product's default tax is a sale tax
                            # (self.tax_sale) — irrelevant to this test and
                            # incompatible with a purchase fiscal position.
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        bill.action_post()

        self.assertEqual(bill.state, "posted")
        self.assertFalse(bill.pt_arxi_atcud)
        self.assertFalse(bill.pt_arxi_inalterable_hash)
