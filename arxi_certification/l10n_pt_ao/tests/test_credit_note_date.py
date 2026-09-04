"""Regression test for the 2026-08-24 fix (UAT 21): a certified credit note
must not be postable with a date earlier than its origin invoice's date.

Also covers the three cases where this check must NOT block, matching the
same gating as the rest of ``_pt_arxi_check_credit_note_origin``: a
supplier credit note (``in_refund``), a non-PT/AO company, and a
non-certified journal (``l10n_cert = False``).
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestCreditNoteDate(AccountTestCertifiedCommon):

    def _reverse(self, invoice, journal=None):
        wizard = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "move_ids": [Command.set(invoice.ids)],
                    "journal_id": (journal or self.sale_journal).id,
                }
            )
        )
        res = wizard.reverse_moves()
        return self.env["account.move"].browse(res["res_id"])

    def test_credit_note_earlier_than_origin_blocked(self):
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()

        credit_note = self._reverse(invoice)
        credit_note.invoice_date = invoice.invoice_date - timedelta(days=5)
        with self.assertRaises(UserError):
            credit_note.action_post()

    def test_credit_note_same_or_later_than_origin_allowed(self):
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()

        credit_note = self._reverse(invoice)
        credit_note.invoice_date = invoice.invoice_date
        credit_note.action_post()
        self.assertEqual(credit_note.state, "posted")

    def test_supplier_credit_note_not_blocked(self):
        """The check only applies to ``out_refund`` — a supplier credit
        note (``in_refund``) with an "early" date must post fine."""
        purchase_journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "journal_id": purchase_journal.id,
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": self.product.lst_price,
                            "tax_ids": [Command.set(self.tax_sale.ids)],
                        }
                    )
                ],
            }
        )
        bill.action_post()

        credit_note = bill.copy(
            {
                "move_type": "in_refund",
                "invoice_date": bill.invoice_date - timedelta(days=30),
            }
        )
        credit_note.action_post()
        self.assertEqual(credit_note.state, "posted")

    def test_non_pt_ao_company_not_blocked(self):
        """A non-PT/AO company must never be blocked by this check."""
        other_company = self.env["res.company"].create(
            {"name": "Non PT/AO Co", "country_id": self.env.ref("base.us").id}
        )
        self.env["account.chart.template"].try_loading(
            "generic_coa", company=other_company
        )
        other_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", other_company.id)],
            limit=1,
        )
        partner = self.env["res.partner"].create(
            {"name": "US Partner", "company_id": False}
        )
        product = self.env["product.product"].create(
            {"name": "US product", "type": "service", "company_id": False}
        )
        invoice = (
            self.env["account.move"]
            .with_company(other_company)
            .create(
                {
                    "move_type": "out_invoice",
                    "journal_id": other_journal.id,
                    "partner_id": partner.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": product.id,
                                "quantity": 1.0,
                                "price_unit": product.lst_price or 10.0,
                            }
                        )
                    ],
                }
            )
        )
        invoice.action_post()

        credit_note = self._reverse(invoice, journal=other_journal)
        credit_note.invoice_date = invoice.invoice_date - timedelta(days=30)
        credit_note.action_post()
        self.assertEqual(credit_note.state, "posted")

    def test_non_certified_journal_not_blocked(self):
        """A credit note on a non-certified journal must not be blocked by
        the origin-date check, even referencing a certified origin
        invoice."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()

        credit_note = self._reverse(invoice, journal=self.uncertified_sale_journal)
        credit_note.invoice_date = invoice.invoice_date - timedelta(days=30)
        credit_note.action_post()
        self.assertEqual(credit_note.state, "posted")
