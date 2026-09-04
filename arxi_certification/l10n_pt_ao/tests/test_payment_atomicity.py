"""Regression test (Dylan, 2026-08-27) — the AO/generic side of the
atomicity guarantee: ``create_payment_lines()`` + ``_pt_arxi_assign_payment_name()``
must be atomic with the rest of a certified customer payment's posting,
same as the PT-specific ATCUD assignment tested in
``l10n_pt_certificate/tests/test_payment_atomicity.py``.

Deliberately uses ``AccountTestCertifiedCommon`` (AO company, no
``l10n_pt_certificate`` installed — no ATCUD/``l10n_pt.account.series``
involved at all): the payment lines and the sequential ``payment_name``
are owned by this module, not by ``l10n_pt_certificate``, and the same
guarantee must hold for AO companies that never touch ATCUD. The PT test
covers the ATCUD-specific half (a different, PT-only mechanism layered on
top via ``additional_receipt_info()``); this one covers the half that's
actually implemented here.
"""

from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestPaymentAtomicityAO(AccountTestCertifiedCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.env["account.journal"].create(
            {
                "name": "Test Bank",
                "type": "bank",
                "code": "TBNK",
                "company_id": cls.company.id,
                "l10n_cert": True,
            }
        )
        for line in (
            cls.bank_journal.inbound_payment_method_line_ids
            | cls.bank_journal.outbound_payment_method_line_ids
        ):
            if not line.payment_account_id:
                line.payment_account_id = cls.env["account.account"].search(
                    [
                        ("company_ids", "in", cls.company.id),
                        ("account_type", "=", "asset_current"),
                    ],
                    limit=1,
                )
        # Own the sequence explicitly: with no l10n_pt_certificate (and no
        # pt_arxi chart hook) installed here, nothing else creates it —
        # _pt_arxi_assign_payment_name() would otherwise silently write
        # payment_name = False (next_by_code() returns None for a missing
        # code) instead of raising, masking exactly the kind of partial
        # state this test exists to rule out.
        cls.env["ir.sequence"].create(
            {
                "name": "Payments customer invoices sequence",
                "code": "account.payment.customer.invoice.cert",
                "prefix": "RG %(range_year)s/",
                "implementation": "no_gap",
                "number_next": 1,
                "number_increment": 1,
                "use_date_range": True,
                "padding": 4,
                "company_id": cls.company.id,
            }
        )

    def _create_payment(self, invoice):
        return self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": invoice.partner_id.id,
                "amount": invoice.amount_total,
                "journal_id": self.bank_journal.id,
                "invoice_ids": [Command.set(invoice.ids)],
                "date": fields.Date.today(),
            }
        )

    def test_downstream_failure_leaves_no_trace(self):
        """A failure right after payment lines + payment_name have been
        computed in-memory, but before the request commits, must roll back
        all of it — no orphaned payment line, no burned payment_name."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()

        # create() lives INSIDE the savepoint too: a real failed request
        # (e.g. via the register-payment wizard) rolls back the payment's
        # own creation along with everything action_post() did — the
        # record must not survive at all, not just come back empty.
        with self.assertRaises(RuntimeError):
            with self.env.cr.savepoint():
                payment = self._create_payment(invoice)
                with patch.object(
                    type(payment),
                    "save_address",
                    side_effect=RuntimeError("simulated downstream failure"),
                ):
                    payment.action_post()

        self.assertFalse(
            self.env["account.payment"].search([("invoice_ids", "in", invoice.ids)]),
            "no payment record at all may survive a rolled-back post",
        )

    def test_normal_flow_still_posts_with_lines_and_name(self):
        """Sanity check: the normal flow still posts with lines and a
        payment_name assigned together."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()
        payment = self._create_payment(invoice)
        payment.action_post()

        self.assertIn(payment.state, ("in_process", "paid"))
        self.assertTrue(payment.payment_name)
        self.assertTrue(payment.payment_line_ids)

    def test_retry_after_failure_creates_no_duplicate(self):
        """Retrying (creating a fresh payment for the same invoice) after a
        rolled-back attempt must succeed cleanly, with no leftover/duplicate
        payment behind from the failed attempt."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()

        with self.assertRaises(RuntimeError):
            with self.env.cr.savepoint():
                failed_payment = self._create_payment(invoice)
                with patch.object(
                    type(failed_payment),
                    "save_address",
                    side_effect=RuntimeError("simulated downstream failure"),
                ):
                    failed_payment.action_post()

        existing = self.env["account.payment"].search(
            [("invoice_ids", "in", invoice.ids)]
        )
        self.assertFalse(
            existing, "the failed attempt must not leave any payment behind"
        )

        retry_payment = self._create_payment(invoice)
        retry_payment.action_post()

        all_payments = self.env["account.payment"].search(
            [("invoice_ids", "in", invoice.ids)]
        )
        self.assertEqual(
            len(all_payments),
            1,
            "retrying must not end up with more than one payment for the "
            "same invoice",
        )
        self.assertEqual(all_payments, retry_payment)
