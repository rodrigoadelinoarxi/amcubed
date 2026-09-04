"""Regression test (Dylan, 2026-08-27): the ATCUD/sequence consumption for a
certified customer payment must be fully atomic with the rest of the posting
— either everything survives (payment lines, ``payment_name``,
``pt_arxi_atcud``, the consumed series number), or none of it does.

Root cause on older branches (``16.0``/``18.0``): ``_get_atcud_for_move``/
``_get_atcud_for_payment`` called ``self.env.cr.commit()`` right after
consuming a series number (one of them even opened an unused separate
cursor, dead code from an even older attempt at isolating that commit). That
commit is independent of whatever runs afterwards in the same request — if
anything downstream then failed (network hiccup, an unrelated validation
error, a worker being recycled), the already-committed series number/ATCUD
survived while the payment lines and the rest of the posting rolled back.
The result: a payment left with a correct ``payment_name``/``pt_arxi_atcud``
but no payment lines — impossible to fix except by hand, and leaving the
series's next expected number permanently out of sync with what the
document sequence would compute (SAF-T export then fails XSD validation).

This was already cleaned up during the 19.0 migration (CMP-010/013/021/025/
026/029 in the migration ledger): no ``cr.commit()`` anywhere in this
chain any more, and the series number is reserved via ``SELECT … FOR
UPDATE`` inside the same transaction as everything else. This test proves
that guarantee holds for the current code: simulating a failure that
happens *after* the ATCUD/sequence logic has already run, but before the
request would actually commit (a ``cr.savepoint()`` — the same rollback
boundary a real HTTP request gets when an exception escapes it) must leave
*zero* trace behind.
"""

from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import tagged

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


@tagged("post_install", "-at_install")
class TestPaymentAtomicity(AccountTestPTInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The common fixture deliberately uses generic_coa, not the real
        # pt_arxi chart (see AccountTestPTInvoicingCommon docstring) — the
        # "account.payment.customer.invoice.cert" sequence that
        # _pt_arxi_assign_payment_name() needs is normally created by
        # pt_arxi's chart template hook (chart_template.py), so it must be
        # created here instead.
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

    def _series_line_count(self):
        doc_type_rg = self.env.ref("l10n_pt_certificate.recibo")
        series = self.env["l10n_pt.account.series"].search(
            [
                ("document_type_id", "=", doc_type_rg.id),
                ("company_id", "=", self.company.id),
            ]
        )
        return sum(len(s.line_ids) for s in series)

    def test_downstream_failure_leaves_no_trace(self):
        """A failure that happens strictly *after* the payment lines,
        ``payment_name`` and ATCUD have already been computed in-memory
        (but before the request commits) must roll back every bit of it —
        no orphaned series number, no half-written payment."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()

        lines_before = self._series_line_count()

        # create() lives INSIDE the savepoint too: a real failed request
        # (e.g. via the register-payment wizard) rolls back the payment's
        # own creation along with everything action_post() did — the
        # record must not survive at all, not just come back empty.
        # save_address() runs right after _pt_arxi_finalize_cert_customer_payment
        # (payment lines + payment_name + ATCUD already assigned) and right
        # before the native account.payment posting — a realistic stand-in
        # for "something unrelated fails further down the same request".
        with self.assertRaises(RuntimeError):
            with self.env.cr.savepoint():
                payment = self.env["account.payment"].create(
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
        self.assertEqual(
            self._series_line_count(),
            lines_before,
            "the series must not have a number consumed for a payment that "
            "never actually posted — a gap here later blocks the sequence "
            "against the series",
        )

    def test_normal_flow_still_posts_with_lines_and_atcud(self):
        """Sanity check: the atomicity guard above doesn't get in the way of
        a normal, successful post — lines, name and ATCUD must all be set
        together."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()

        payment = self.env["account.payment"].create(
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
        payment.action_post()

        self.assertIn(payment.state, ("in_process", "paid"))
        self.assertTrue(payment.payment_name)
        self.assertTrue(payment.pt_arxi_atcud)
        self.assertTrue(payment.payment_line_ids)
