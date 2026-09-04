"""Regression test (UAT 13d): duplicating an ``l10n_pt.account.series``
crashed immediately, server-side, with a raw ``NotNullViolation`` on
``code`` — before the user ever saw a form to enter a new one.

``code`` is required *and* ``copy=False`` (correct: an AT series code
must never be silently reused), so ``copy()`` left it out of the created
vals entirely, violating the column's NOT NULL constraint.
"""
from odoo import fields
from odoo.tests import tagged

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


@tagged("post_install", "-at_install")
class TestSeriesDuplicate(AccountTestPTInvoicingCommon):

    def _create_series(self, code="ORIG26"):
        return self.env["l10n_pt.account.series"].create(
            {
                "code": code,
                "name": "Original Series",
                "document_type_id": self.document_type_ft.id,
                "invoicing_journal_id": self.sale_journal.id,
                "company_id": self.company.id,
                "initial_date": fields.Date.today(),
            }
        )

    def test_duplicate_draft_series_does_not_crash(self):
        series = self._create_series()
        duplicate = series.copy()
        self.assertEqual(duplicate.state, "draft")
        self.assertEqual(duplicate.code, "")

    def test_duplicate_active_series_does_not_crash(self):
        series = self._create_series()
        series.action_activate()
        self.assertEqual(series.state, "active")

        duplicate = series.copy()
        self.assertEqual(duplicate.state, "draft")
        self.assertEqual(duplicate.code, "")
        # Registration fields must never carry over to the copy either.
        self.assertFalse(duplicate.validation_code)

    def test_duplicate_does_not_carry_over_consumed_lines(self):
        """A series that already numbered documents must not have those
        lines copied onto the duplicate — they belong to the original
        series' numbering chain, not a fresh one."""
        series = self._create_series()
        self.env["l10n_pt.account.series.line"].create(
            {
                "series_id": series.id,
                "sequence_number": 1,
                "res_model": "res.partner",
                "res_id": self.partner.id,
            }
        )
        self.assertTrue(series.line_ids)

        duplicate = series.copy()
        self.assertFalse(duplicate.line_ids)
