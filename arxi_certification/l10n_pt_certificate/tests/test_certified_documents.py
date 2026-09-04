from odoo import Command, fields

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_l10n_pt_common import AccountTestPTInvoicingCommon

# Same regex account_move.py enforces on the document name (FT SERIES/0001).
PT_CERTIFIED_SEQUENCE = (
    r"^(?P<doc_type>(FT|FR|FS|NC|ND))\s(?P<series_code>\w+)\/(?P<seq>\d+)$"
)


@tagged("post_install", "-at_install")
class TestCertifiedDocuments(AccountTestPTInvoicingCommon):
    """AT-specific field generation on certified (l10n_cert=True) PT sale
    documents: hashing, ATCUD, sequencing, QR code and the resulting
    immutability. The general (country-agnostic) certification rules —
    negative-line/reference checks, partner/product locking,
    credit-note-origin tracing — are tested in ``l10n_pt_ao`` instead, since
    that's where they're implemented."""

    def test_posting_assigns_hash_atcud_and_sequence(self):
        """A posted certified invoice gets a hash, an ATCUD and a name in the
        AT sequence format."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()

        self.assertTrue(
            move.pt_arxi_inalterable_hash, "Certified invoice must be hashed on posting"
        )
        self.assertTrue(
            move.pt_arxi_atcud, "Certified invoice must get an ATCUD on posting"
        )
        self.assertTrue(
            move.pt_arxi_validated_date,
            "Certified invoice must get a system entry date",
        )
        self.assertRegex(move.name, PT_CERTIFIED_SEQUENCE)
        self.assertIn(
            "-", move.pt_arxi_atcud, "ATCUD must be '<validation_code>-<seq>'"
        )

    def test_hash_chain_between_consecutive_documents(self):
        """The second certified document in a series gets a distinct hash and
        a sequential ATCUD, chained to the first one via
        ``_pt_arxi_hash_moves``'s sequence_number lookup (not
        ``get_previous_document``, which orders by validated_date — too
        timestamp-precision-sensitive for a fast, same-second test)."""
        move_1 = self._create_invoice(self.sale_journal)
        move_1.action_post()
        move_2 = self._create_invoice(self.sale_journal)
        move_2.action_post()

        self.assertNotEqual(
            move_1.pt_arxi_inalterable_hash, move_2.pt_arxi_inalterable_hash
        )
        self.assertEqual(move_1.name, "FT %s/0001" % move_1.date.year)
        self.assertEqual(move_2.name, "FT %s/0002" % move_2.date.year)
        self.assertTrue(move_1.pt_arxi_atcud.endswith("-0001"))
        self.assertTrue(move_2.pt_arxi_atcud.endswith("-0002"))

    def test_qr_code_data_populated_after_posting(self):
        """The AT QR code data string is only built once the document is posted
        and includes the ATCUD (field H) and the hash-derived signature (field Q)."""
        move = self._create_invoice(self.sale_journal)
        self.assertEqual(move.data_for_qr_code(), "", "Draft documents have no QR data")
        move.action_post()

        qr_data = move.data_for_qr_code()
        self.assertIn("H:%s" % move.pt_arxi_atcud, qr_data)
        self.assertRegex(qr_data, r"Q:[0-9a-fA-F]{4}")

    def test_posted_certified_document_cannot_reset_to_draft(self):
        """Once hashed, a certified document is immutable — it cannot be reset
        to draft (native restrict_mode_hash_table lock triggered by the AT
        hash being set)."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()

        with self.assertRaises(UserError):
            move.button_draft()

    def _create_and_post_certified_receipt(self, invoice):
        """Certified customer receipt (RG) paying ``invoice`` in full, on a
        certified bank/cash journal."""
        payment_journal = self.env["account.journal"].search(
            [("company_id", "=", self.company.id), ("type", "in", ("bank", "cash"))],
            limit=1,
        )
        payment_journal.l10n_cert = True
        # PaymentMethodLine._set_default_payment_account_id() (l10n_pt_certificate)
        # only fills payment_account_id via the pt_arxi chart template's
        # fixed account xmlids (account.<company>_chart_128/129) — this
        # suite uses generic_coa instead (see test_l10n_pt_common.py), so
        # those xmlids don't exist and the line is left with no Outstanding
        # Account, which native Odoo requires before it'll post a payment.
        # Same fallback used in l10n_pt_ao/tests/test_payment_no_invoice.py.
        for line in payment_journal.inbound_payment_method_line_ids:
            if not line.payment_account_id:
                line.payment_account_id = self.env["account.account"].search(
                    [
                        ("company_ids", "in", self.company.id),
                        ("account_type", "=", "asset_current"),
                    ],
                    limit=1,
                )
        # Only created by the pt_arxi chart template's post-install hook
        # (see chart_template.py) — this suite uses generic_coa instead
        # (see test_l10n_pt_common.py), so it's missing here.
        if not self.env["ir.sequence"].search_count(
            [
                ("code", "=", "account.payment.customer.invoice.cert"),
                ("company_id", "=", self.company.id),
            ]
        ):
            self.env["ir.sequence"].create(
                {
                    "name": "Payments customer invoices sequence",
                    "code": "account.payment.customer.invoice.cert",
                    "prefix": "RG %(range_year)s/",
                    "implementation": "no_gap",
                    "number_next": 1,
                    "number_increment": 1,
                    "use_date_range": True,
                    "padding": 4,
                    "company_id": self.company.id,
                }
            )
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": invoice.partner_id.id,
                "amount": invoice.amount_total,
                "journal_id": payment_journal.id,
                "invoice_ids": [Command.set(invoice.ids)],
                "date": fields.Date.today(),
            }
        )
        payment.action_post()
        return payment

    def test_certified_receipt_cannot_be_reset_to_draft(self):
        """A hashed certified receipt can't be reset to draft — only
        annulled. Native's own hash lock doesn't fire here: receipts are
        hashed via the decoupled ``pt_arxi_inalterable_hash`` pipeline
        (``_pt_arxi_hash_moves``), not the native
        ``restrict_mode_hash_table``/``inalterable_hash`` mechanism (certified
        bank/cash journals don't set ``restrict_mode_hash_table``)."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()
        payment = self._create_and_post_certified_receipt(invoice)

        self.assertTrue(payment.move_id.pt_arxi_inalterable_hash)
        self.assertFalse(payment.move_id.inalterable_hash)

        with self.assertRaises(UserError):
            payment.move_id.button_draft()

    def test_certified_receipt_cannot_be_deleted(self):
        """A hashed certified receipt is fiscally relevant (reported in the
        SAF-T even once cancelled) and can only be annulled, never
        deleted — whether still posted or already cancelled."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()
        payment = self._create_and_post_certified_receipt(invoice)

        with self.assertRaises(UserError):
            payment.unlink()

        payment.action_cancel()
        self.assertEqual(payment.state, "canceled")
        self.assertTrue(
            payment.move_id.pt_arxi_inalterable_hash,
            "Cancelling must not clear the certification hash",
        )
        with self.assertRaises(UserError):
            payment.unlink()

    def test_draft_receipt_can_still_be_deleted(self):
        """A receipt that was never posted (no hash) can be deleted
        normally — the restriction only applies once hashed."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()
        payment_journal = self.env["account.journal"].search(
            [("company_id", "=", self.company.id), ("type", "in", ("bank", "cash"))],
            limit=1,
        )
        payment_journal.l10n_cert = True
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": invoice.partner_id.id,
                "amount": invoice.amount_total,
                "journal_id": payment_journal.id,
                "invoice_ids": [Command.set(invoice.ids)],
                "date": fields.Date.today(),
            }
        )
        self.assertEqual(payment.state, "draft")
        self.assertFalse(payment.move_id.pt_arxi_inalterable_hash)

        payment.unlink()
        self.assertFalse(payment.exists())
