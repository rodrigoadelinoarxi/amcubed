from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPtArxiChartTemplate(TransactionCase):
    """Regression test for pendência #15 (migration ledger): the ``pt_arxi``
    chart template's account/group/tax-group/fiscal-position CSVs
    (``data/template/*-pt_arxi.csv``) were dropped without being ported when
    the old ``l10n_pt_arxi_coa`` module was absorbed into this one — a brand
    new PT company loading the real chart (as opposed to the ``generic_coa``
    used by the rest of this test suite) got only Odoo's generic fallback
    accounts, not the ~1540-account SNC taxonomy.

    Doesn't cover ``account.tax`` (owned by ``l10n_pt_reports_arxi``, not
    installed here) — only what this module itself is responsible for."""

    def test_load_pt_arxi_chart_creates_full_account_data(self):
        """Loading the real ``pt_arxi`` chart on a new PT company must not
        raise, and must populate accounts/groups/tax groups/fiscal
        positions from this module's own CSVs — not just Odoo's generic
        fallback accounts."""
        company = self.env["res.company"].create(
            {
                "name": "ARXI PT Chart Test Company",
                "country_id": self.env.ref("base.pt").id,
                "currency_id": self.env.ref("base.EUR").id,
                "vat": "PT123456789",
                "entity_type": "S",
                "commercial_registry": "LISBOA",
                "company_registry": "123456789",
                "street": "Rua Teste, 1",
                "city": "Lisboa",
                "zip": "1000-001",
                "l10n_pt_at_test": True,
                "tax_calculation_rounding_method": "round_globally",
            }
        )
        self.env.user.write({"company_ids": [Command.link(company.id)]})
        self.env = self.env(
            context=dict(self.env.context, allowed_company_ids=company.ids)
        )
        company = company.with_env(self.env)

        self.env["account.chart.template"].try_loading("pt_arxi", company=company)

        self.assertGreater(
            self.env["account.account"].search_count(
                [("company_ids", "in", company.id)]
            ),
            1000,
            "Expected the full SNC account taxonomy (~1540 accounts), not "
            "just Odoo's generic fallback accounts.",
        )
        self.assertGreater(
            self.env["account.group"].search_count([("company_id", "=", company.id)]),
            500,
        )
        self.assertGreater(
            self.env["account.tax.group"].search_count(
                [("company_id", "=", company.id)]
            ),
            10,
        )
        fiscal_positions = self.env["account.fiscal.position"].search(
            [("company_id", "=", company.id)]
        )
        self.assertEqual(len(fiscal_positions), 5)

        # The regional VAT-rate replacement mapping (mainland -> Açores/
        # Madeira) migrated from the old account.fiscal.position.tax
        # junction model (removed in this Odoo version) onto
        # account.tax.original_tax_ids/fiscal_position_ids — check the
        # company-level default receivable/payable accounts resolved too
        # (property_account_receivable_id: "chart_21111" etc. in
        # template_pt_arxi.py), since that's what the original bug report
        # actually crashed on.
        self.assertTrue(company.account_default_pos_receivable_account_id)

        # UAT 9 (Paulo): "Conta de Receitas Predefinida" empty by default on
        # the sale journal — native Odoo only fills account.journal's
        # default_account_id via an @api.onchange('type'), which never
        # fires when the chart template bulk-creates these journals.
        sale_journal = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "sale")], limit=1
        )
        purchase_journal = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "purchase")], limit=1
        )
        self.assertEqual(sale_journal.default_account_id.code, "7111")
        self.assertEqual(purchase_journal.default_account_id.code, "3111")
