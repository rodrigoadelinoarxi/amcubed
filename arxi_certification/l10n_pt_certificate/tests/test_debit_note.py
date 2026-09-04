"""Regression tests for certified debit notes (ND) — verified end-to-end
against the AT/SAF-T rules (2026-08-25): own document type/series/ATCUD,
mandatory reason, every line linked back to its origin line
(``refunded_line_id``, consumed by the SAF-T ``References`` block), and
``invoice_type_to_saft()`` reporting "ND" (confirmed by generating a real
SAF-T export and inspecting the XML — the ND entry carries
``InvoiceType>ND``, ``ATCUD``, ``Hash`` and a ``References`` block
pointing back at the origin invoice with the reason, exactly like the
credit note path; no code gap found there — only the printed/PDF title
translation was missing, fixed separately).
"""
from odoo.exceptions import UserError

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


class TestDebitNote(AccountTestPTInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reason = cls.env["account.move.reason"].create(
            {"name": "Erro de faturação", "reason_type": "both"}
        )

    def _create_and_post_invoice(self):
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()
        return invoice

    def test_debit_note_requires_a_reason(self):
        invoice = self._create_and_post_invoice()
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({})
        with self.assertRaises(UserError):
            wizard.create_debit()

    def _create_debit_note(self, invoice):
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({"reason_id": self.reason.id})
        action = wizard.create_debit()
        return self.env["account.move"].browse(
            [action["res_id"]] if action.get("res_id") else action["domain"][0][2]
        )

    def test_debit_note_gets_own_document_type_and_origin_link(self):
        invoice = self._create_and_post_invoice()
        nd = self._create_debit_note(invoice)

        self.assertEqual(nd.document_type_id.code, "ND")
        self.assertEqual(nd.debit_origin_id, invoice)
        self.assertEqual(nd.reason, self.reason.name)

        product_lines = nd.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        )
        self.assertTrue(product_lines)
        self.assertTrue(all(product_lines.mapped("refunded_line_id")))

    def test_debit_note_gets_own_atcud_distinct_from_origin(self):
        invoice = self._create_and_post_invoice()
        nd = self._create_debit_note(invoice)
        nd.action_post()

        self.assertEqual(nd.state, "posted")
        self.assertTrue(nd.pt_arxi_inalterable_hash)
        self.assertTrue(nd.pt_arxi_atcud)
        self.assertNotEqual(nd.pt_arxi_atcud, invoice.pt_arxi_atcud)
        # Own numbering chain: "ND <series>/0001", not the invoice's "FT ...".
        self.assertTrue(nd.name.startswith("ND "))

    def test_debit_note_reports_nd_to_saft(self):
        invoice = self._create_and_post_invoice()
        nd = self._create_debit_note(invoice)
        nd.action_post()

        self.assertEqual(nd.invoice_type_to_saft(), "ND")
        self.assertEqual(invoice.invoice_type_to_saft(), "FT")

    def test_debit_note_requires_every_line_linked_to_origin(self):
        """A certified debit note line without refunded_line_id must be
        rejected at posting — every line must trace back to the original
        document (AT rule, shared with credit notes)."""
        invoice = self._create_and_post_invoice()
        nd = self._create_debit_note(invoice)
        nd.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        ).write({"refunded_line_id": False})
        with self.assertRaises(Exception):
            nd.action_post()
