"""Regression test for the 2026-08-24 fix: a certified customer payment
must never post without a partner or an origin invoice.

Root cause of the gap: a certified customer payment created with an empty
``partner_id`` (native Odoo allows it — ``partner_id`` isn't
``required=True``) used to silently skip
``_pt_arxi_finalize_cert_customer_payment`` entirely — the old condition
gating it also required ``rec.partner_id`` — bypassing the "must have an
origin invoice" check (and the sequence-order/ATCUD steps) along with
everything else. It only accidentally failed later, deep inside the
unrelated hashing pipeline (``_pt_arxi_calculate_hashes``), with a
confusing "Payment sequence not found" error instead of a clear one.
``action_post`` now raises an explicit, clear error when a certified
customer payment has no partner, before any of that.
"""

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestPaymentNoInvoice(AccountTestCertifiedCommon):
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

    def _create_payment(self, partner=None, amount=100.0):
        vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "amount": amount,
            "journal_id": self.bank_journal.id,
            "date": fields.Date.today(),
        }
        if partner is not None:
            vals["partner_id"] = partner.id
        return self.env["account.payment"].create(vals)

    def test_payment_with_partner_without_invoice_blocked(self):
        payment = self._create_payment(partner=self.partner)
        with self.assertRaises(ValidationError):
            payment.action_post()

    def test_payment_without_partner_without_invoice_blocked(self):
        payment = self._create_payment(partner=None)
        with self.assertRaises(ValidationError):
            payment.action_post()

    def test_payment_with_invoice_still_allowed(self):
        """The fix must not regress the normal, correct flow: a certified
        customer payment with a real origin invoice still posts fine."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": invoice.partner_id.id,
                "amount": invoice.amount_total,
                "journal_id": self.bank_journal.id,
                "invoice_ids": [(6, 0, invoice.ids)],
                "date": fields.Date.today(),
            }
        )
        payment.action_post()
        self.assertEqual(payment.state, "in_process")

    def test_outbound_customer_payment_without_invoice_blocked(self):
        """UAT 34c follow-up (Paulo, 2026-08-26): switching a certified
        customer payment's direction to "Send" (outbound — partner_type
        stays 'customer') skipped the entire certification pipeline,
        including the "no payment without an origin invoice" check —
        ``_pt_arxi_is_cert_customer_payment()`` requires
        ``payment_type == 'inbound'``, and only that path calls
        ``create_payment_lines()``. Reproduced: it posted with no
        invoice/payment lines at all, no error. This rule must hold
        regardless of direction."""
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 50.0,
                "journal_id": self.bank_journal.id,
                "date": fields.Date.today(),
            }
        )
        with self.assertRaises(ValidationError):
            payment.action_post()

    def test_outbound_internal_transfer_without_invoice_allowed(self):
        """Dylan (2026-08-27): the outbound-without-origin block above must
        not catch internal transfers (payment_internal_transfer, when
        installed) — moving money between a company's own journals is
        never a customer receipt with an origin invoice, no matter what
        partner_type/payment_type the transfer leg happens to carry.

        Reproduced live: an inbound internal transfer was blocked by this
        exact "no origin invoice" error, because payment_internal_transfer's
        own action_post() override — the one that sets
        ``self.env.context['internal_transfer'] = True`` — runs *after*
        this module's in account.payment's MRO (l10n_pt_ao's action_post()
        calls into these checks first, then super() eventually reaches
        payment_internal_transfer's). The context is therefore never set
        yet when these checks run; the fix checks the ``is_internal_transfer``
        field directly instead (set on the record itself, unaffected by
        call order) — this only exercises that path if
        payment_internal_transfer happens to be installed alongside this
        module in the test run, since l10n_pt_ao deliberately doesn't
        depend on it."""
        if "is_internal_transfer" not in self.env["account.payment"]._fields:
            self.skipTest("payment_internal_transfer not installed in this test run")
        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 50.0,
                "journal_id": self.bank_journal.id,
                "destination_journal_id": self._create_destination_journal().id,
                "is_internal_transfer": True,
                "date": fields.Date.today(),
            }
        )
        payment.action_post()
        self.assertIn(payment.state, ("in_process", "paid"))

    def test_inbound_internal_transfer_without_invoice_allowed(self):
        """Same as above, but the direction actually reported live
        (Dylan, screenshot 2026-08-27): "Receive" + Internal Transfer
        ticked, blocked before this fix by
        ``_pt_arxi_is_cert_customer_payment()`` routing it through the
        full certified-receipt pipeline (which requires an origin
        invoice)."""
        if "is_internal_transfer" not in self.env["account.payment"]._fields:
            self.skipTest("payment_internal_transfer not installed in this test run")
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "amount": 50.0,
                "journal_id": self.bank_journal.id,
                "destination_journal_id": self._create_destination_journal().id,
                "is_internal_transfer": True,
                "date": fields.Date.today(),
            }
        )
        payment.action_post()
        self.assertIn(payment.state, ("in_process", "paid"))
        self.assertFalse(payment.payment_name)
        self.assertFalse(payment.payment_line_ids)

    def _create_destination_journal(self):
        """A second certified journal for the internal-transfer tests
        above — payment_internal_transfer needs a distinct
        destination_journal_id to compute destination_account_id (and
        post a valid journal entry) for the transfer."""
        journal = self.env["account.journal"].create(
            {
                "name": "Test Cash",
                "type": "cash",
                "code": "TCASH",
                "company_id": self.company.id,
                "l10n_cert": True,
            }
        )
        for line in (
            journal.inbound_payment_method_line_ids
            | journal.outbound_payment_method_line_ids
        ):
            if not line.payment_account_id:
                line.payment_account_id = self.env["account.account"].search(
                    [
                        ("company_ids", "in", self.company.id),
                        ("account_type", "=", "asset_current"),
                    ],
                    limit=1,
                )
        return journal

    def test_outbound_customer_payment_with_credit_note_still_allowed(self):
        """The fix must not regress a real refund: an outbound customer
        payment reconciled against a credit note still posts fine."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()
        credit_note = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "journal_id": invoice.journal_id.id,
                "partner_id": invoice.partner_id.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": self.product.lst_price,
                            "tax_ids": [(6, 0, self.tax_sale.ids)],
                            "refunded_line_id": invoice.invoice_line_ids.filtered(
                                lambda l: l.display_type == "product"
                            )[:1].id,
                        },
                    )
                ],
            }
        )
        credit_note.action_post()
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=credit_note.ids)
            .create({"journal_id": self.bank_journal.id})
        )
        wizard.action_create_payments()
        payment = self.env["account.payment"].search(
            [("invoice_ids", "in", credit_note.ids)]
        )
        self.assertEqual(payment.payment_type, "outbound")
        self.assertEqual(payment.state, "paid")
