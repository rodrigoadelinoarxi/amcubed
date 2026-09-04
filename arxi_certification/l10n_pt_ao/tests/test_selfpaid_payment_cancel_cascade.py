"""Regression test (PQC 2026-08): cancelling a self-paid invoice's
auto-payment — directly, or via its own journal entry — must also cancel
the invoice. Before this fix, only the payment (and its reconciliation)
was cancelled: the certified invoice stayed "Posted" even though its
whole compliance model requires it to be auto-paid, leaving it posted
with no valid payment behind it.

The fix (``AccountPayment.action_cancel`` /
``_pt_arxi_cancel_selfpaid_invoices``) lives in this module and is gated
on ``company_id.country_code in ('PT', 'AO')``, not on anything
PT-specific — the self-paid *document* concept (FS/FR, ATCUD, hash) is
PT-only and lives in ``l10n_pt_certificate``, but the cascade itself only
needs a payment with ``is_selfpaid=True`` linked to a posted invoice, so
it's exercised here directly without that module's document-type/ATCUD
machinery. See ``l10n_pt_certificate/tests`` for the end-to-end FS/FR
flow (auto-payment creation on posting).
"""
from odoo import Command, fields

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


class TestSelfpaidPaymentCancelCascade(AccountTestCertifiedCommon):

    def _create_and_pay_invoice(self, price_unit=50.0):
        invoice = self._create_invoice(self.sale_journal, price_unit=price_unit)
        invoice.action_post()

        payment_journal = self.env["account.journal"].create(
            {
                "name": "Certified Bank",
                "type": "bank",
                "code": "CBNK",
                "company_id": self.company.id,
                "l10n_cert": True,
            }
        )
        outstanding_account = self.env["account.account"].create(
            {
                "name": "Outstanding Test Account",
                "code": "OUTSTCASC",
                "account_type": "asset_current",
                "reconcile": True,
                "company_ids": [Command.set(self.company.ids)],
            }
        )
        payment_journal.inbound_payment_method_line_ids.payment_account_id = (
            outstanding_account
        )
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"journal_id": payment_journal.id})
        )
        wizard.action_create_payments()
        payment = self.env["account.payment"].search(
            [("invoice_ids", "in", invoice.ids)]
        )
        return invoice, payment

    def test_cancelling_selfpaid_payment_cancels_the_invoice(self):
        invoice, payment = self._create_and_pay_invoice()
        self.assertEqual(invoice.state, "posted")
        # Marked self-paid by hand — the auto-creation itself is exercised
        # in l10n_pt_certificate; this test is only about the cascade.
        payment.is_selfpaid = True

        payment.action_cancel()

        self.assertEqual(payment.state, "canceled")
        self.assertEqual(
            invoice.state,
            "cancel",
            "The self-paid invoice must be cancelled along with its payment",
        )

    def test_cancelling_a_normal_payment_does_not_touch_unrelated_invoices(self):
        """Sanity check: the cascade is scoped to self-paid payments only —
        a regular (non-self-paid) payment cancellation must not cancel
        any invoice."""
        invoice, payment = self._create_and_pay_invoice()
        self.assertFalse(payment.is_selfpaid)

        other_invoice = self._create_invoice(self.sale_journal, price_unit=200.0)
        other_invoice.action_post()

        payment.action_cancel()

        self.assertEqual(payment.state, "canceled")
        self.assertEqual(
            invoice.state,
            "posted",
            "A non-self-paid payment's cancellation must not cascade to its invoice",
        )
        self.assertEqual(other_invoice.state, "posted")
