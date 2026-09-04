""""Balancetes Portugueses" (Analytic/General Trial Balance) always came
back empty on screen, for every company, regardless of how much posted
data existed. Root cause: this module's 4 reports (analytic_balance_report
and its 3 siblings, data/analytic_ledger.xml) delegate their line
generation to the native account.general.ledger.report.handler
(models/account_analytic_ledger_report.py's _dynamic_lines_generator),
but never declared a line_ids of their own — something v19's native
General Ledger report now requires (data/general_ledger.xml gained this
block going from v18 to v19; the report worked fine without it in v18).
With no line_ids, the native handler had nothing to group/report on.

Confirmed live on a real staging dump (2026-08-28, Dylan): a company with
88 posted move lines/€5040.12 for the selected month rendered zero rows.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_pt_certificate.tests.test_l10n_pt_common import (
    AccountTestPTInvoicingCommon,
)


@tagged("post_install", "-at_install")
class TestAnalyticLedgerReport(AccountTestPTInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        invoice = cls._create_invoice(cls, cls.sale_journal)
        invoice.action_post()
        cls.invoice = invoice

    def _get_report_lines(self, xmlid):
        report = self.env.ref(f"l10n_pt_reports_arxi.{xmlid}").with_company(
            self.company
        )
        options = report.get_options(
            {
                "date": {
                    "date_from": self.invoice.invoice_date.replace(day=1).isoformat(),
                    "date_to": self.invoice.invoice_date.isoformat(),
                    "filter": "custom",
                    "mode": "range",
                },
            }
        )
        return report._get_lines(options)

    def test_analytic_balance_report_not_empty(self):
        lines = self._get_report_lines("analytic_balance_report")
        self.assertTrue(lines, "must have at least the total line")
        self.assertGreater(
            len(lines), 1, "must show account rows, not just the total"
        )

    def test_analytic_balance_closing_report_not_empty(self):
        lines = self._get_report_lines("analytic_balance_closing_report")
        self.assertGreater(len(lines), 1)

    def test_general_balance_report_not_empty(self):
        lines = self._get_report_lines("general_balance_report")
        self.assertGreater(len(lines), 1)

    def test_general_balance_closing_report_not_empty(self):
        lines = self._get_report_lines("general_balance_closing_report")
        self.assertGreater(len(lines), 1)
