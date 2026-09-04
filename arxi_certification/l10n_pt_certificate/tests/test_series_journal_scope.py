"""Regression tests for the 2026-08-20 fix: a certified journal without its
own active series must never reuse (borrow) the active series of another
journal — it must either auto-create its own series, or raise if automatic
creation is disabled.

Before the fix, ``_get_at_series``/``_get_atcud_for_move`` fell back to a
search with no journal filter at all whenever the journal-scoped search
came up empty, picking up any other active series for the same document
type/company — even one already mapped to a different journal.

See the migration ledger entry "l10n_pt_certificate: séries AT não podem
'emprestar' a série de outro diário" and commits ``49618bcd``/``d34080eb``
(``18.0``) / ``f07b2892`` (``19.0-test``).
"""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_l10n_pt_common import AccountTestPTInvoicingCommon


@tagged("post_install", "-at_install")
class TestSeriesJournalScope(AccountTestPTInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Journal Y: same document type as the common sale_journal (X), but
        # with its own active series already registered — the "other
        # journal" whose series must never be borrowed by X.
        cls.other_sale_journal = cls.env["account.journal"].create(
            {
                "name": "Other Certified Sales",
                "type": "sale",
                "code": "FTY",
                "company_id": cls.company.id,
                "l10n_cert": True,
                "source_billing": "P",
                "document_type_id": cls.document_type_ft.id,
                "restrict_mode_hash_table": True,
                "refund_sequence": True,
            }
        )
        cls.other_series = cls.env["l10n_pt.account.series"].create(
            {
                "code": "OTHERY26",
                "name": "Series of the other journal",
                "document_type_id": cls.document_type_ft.id,
                "invoicing_journal_id": cls.other_sale_journal.id,
                "company_id": cls.company.id,
                "state": "active",
                "initial_date": fields.Date.today(),
            }
        )

    def test_series_auto_created_for_own_journal_not_borrowed(self):
        """Journal X has no series of its own; journal Y (same document
        type) has an active one. Posting on X must auto-create X's own
        series — never reuse Y's."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()

        self.assertTrue(move.pt_arxi_atcud)
        validation_code = move.pt_arxi_atcud.split("-")[0]
        self.assertNotEqual(
            validation_code,
            self.other_series.validation_code,
            "the invoice's ATCUD must not use journal Y's validation code",
        )

        own_series = self.env["l10n_pt.account.series"].search(
            [
                ("invoicing_journal_id", "=", self.sale_journal.id),
                ("document_type_id", "=", self.document_type_ft.id),
                ("state", "=", "active"),
            ]
        )
        self.assertEqual(
            len(own_series),
            1,
            "a series should have been auto-created for journal X",
        )
        self.assertNotEqual(own_series, self.other_series)

    def test_series_raises_when_auto_create_disabled(self):
        """With automatic series creation disabled, journal X (no series of
        its own) must raise instead of silently borrowing journal Y's
        series."""
        self.company.l10n_pt_series_auto_create = False
        move = self._create_invoice(self.sale_journal)

        with self.assertRaises(UserError):
            move.action_post()
