"""Modelo 32 ("Mapa de Reintegrações e Amortizações", a fixed-asset
depreciation schedule) was showing deferred expenses/revenues alongside
real fixed assets — confirmed live on a staging dump (2026-08-28, Dylan):
a deferral asset appeared in the report. Deferrals (deferral_type set by
the optional deferrals_option module) are a different accounting concept
and must never be counted here.

Skipped entirely when deferrals_option isn't installed — there's nothing
to exclude, and the field this test depends on doesn't exist.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_pt_certificate.tests.test_l10n_pt_common import (
    AccountTestPTInvoicingCommon,
)


@tagged("post_install", "-at_install")
class TestAssets32Report(AccountTestPTInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "deferral_type" not in cls.env["account.asset"]._fields:
            return

        deferral_account = cls.env["account.account"].with_company(cls.company).create(
            {
                "name": "Deferred Expenses (test)",
                "code": "281",
                "account_type": "asset_current",
                "company_ids": [Command.set([cls.company.id])],
            }
        )
        expense_account = cls.env["account.account"].with_company(cls.company).create(
            {
                "name": "Expense (test)",
                "code": "62999",
                "account_type": "expense",
                "company_ids": [Command.set([cls.company.id])],
            }
        )
        assert deferral_account.account_asset_type == "expense", (
            "test setup relies on the account_asset_type compute picking "
            "up the 281 prefix correctly"
        )
        cls.deferral_asset = cls.env["account.asset"].with_company(cls.company).create(
            {
                "name": "Deferral (test)",
                "original_value": 1000.0,
                "account_depreciation_id": deferral_account.id,
                "account_depreciation_expense_id": expense_account.id,
                "journal_id": cls.sale_journal.id,
                "acquisition_date": "2026-01-01",
                "method_number": 12,
                "method_period": "1",
            }
        )

    def test_deferral_excluded_from_modelo_32(self):
        if "deferral_type" not in self.env["account.asset"]._fields:
            self.skipTest("deferrals_option not installed")
        self.assertEqual(self.deferral_asset.deferral_type, "expense")

        report = self.env.ref("l10n_pt_reports_arxi.assets_report").with_company(
            self.company
        )
        options = report.get_options(
            {
                "date": {
                    "date_from": "2026-01-01",
                    "date_to": "2026-12-31",
                    "filter": "custom",
                    "mode": "range",
                },
            }
        )
        lines = report._get_lines(options)
        names = [l.get("name") for l in lines]
        self.assertNotIn(
            "Deferral (test)", names,
            "Modelo 32 is a fixed-asset depreciation schedule — deferred "
            "expenses/revenues must never appear in it",
        )
