"""Regression test for the 2026-08-21 fix (UAT 29b): a payment posted in a
foreign currency with no exchange rate configured for it must be blocked,
not silently certified at a 1:1 rate.

Root cause: native Odoo's ``res.currency._get_rates()`` falls back to
``1.0`` (``COALESCE(rate_at_date, earliest_rate, 1.0)``) when there isn't a
single ``res.currency.rate`` row for that currency — so e.g. a 10 USD
receipt would be posted/shown as 10 EUR instead of applying the real
exchange rate. ``_pt_arxi_check_currency_rate_configured`` (called from
``action_post``) makes this a hard error instead.
"""
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestPaymentCurrencyRate(AccountTestCertifiedCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.env["account.journal"].create(
            {
                "name": "Test Bank",
                "type": "bank",
                "code": "TBNK",
                "company_id": cls.company.id,
            }
        )
        # A currency genuinely different from the test company's own
        # (AccountTestCertifiedCommon's generic_coa company defaults to
        # USD) — pick one explicitly instead of assuming.
        cls.foreign_currency = cls.env.ref(
            "base.EUR" if cls.company.currency_id != cls.env.ref("base.EUR") else "base.GBP"
        )
        cls.foreign_currency.sudo().active = True
        # Start from a clean slate: no exchange rate at all for this
        # currency, on this company or globally — the exact scenario that
        # made _get_rates() fall back to 1.0.
        cls.env["res.currency.rate"].sudo().search(
            [("currency_id", "=", cls.foreign_currency.id)]
        ).unlink()

    def _create_payment(self, currency, amount=10.0):
        return self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner.id,
                "amount": amount,
                "currency_id": currency.id,
                "journal_id": self.bank_journal.id,
                "date": fields.Date.today(),
            }
        )

    def test_foreign_currency_payment_blocked_without_rate(self):
        payment = self._create_payment(self.foreign_currency)
        with self.assertRaises(ValidationError):
            payment.action_post()

    def test_foreign_currency_payment_allowed_once_rate_exists(self):
        self.env["res.currency.rate"].sudo().create(
            {
                "currency_id": self.foreign_currency.id,
                "name": fields.Date.today(),
                "rate": 0.9,
                "company_id": self.company.id,
            }
        )
        payment = self._create_payment(self.foreign_currency)
        payment.action_post()
        self.assertEqual(payment.state, "in_process")
        # 10 units at rate 0.9 (company currency per foreign currency unit)
        # must NOT equal the numeric 1:1 fallback that this fix prevents.
        self.assertAlmostEqual(payment.amount_company, 10.0 / 0.9, places=2)

    def test_company_currency_payment_not_affected(self):
        """A payment in the company's own currency never needs a rate —
        the check must not touch it at all."""
        payment = self._create_payment(self.company.currency_id)
        payment.action_post()
        self.assertEqual(payment.state, "in_process")
