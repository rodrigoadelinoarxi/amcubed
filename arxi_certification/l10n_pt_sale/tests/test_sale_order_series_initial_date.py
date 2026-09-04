"""UAT vendas/stock, ponto 15 (2026-08-27): a sale order dated before a
series' initial date must never be allowed through — not even when no
series exists yet for that year and ``get_atcud_for_sale()`` auto-creates
one on the spot. Before this fix, that auto-create branch skipped the
date check entirely (it only ran when a series already existed), so a
document dated in a past year with no series yet for that year sailed
through silently and even created (and committed) a brand-new series for
it — reproduced live per the UAT tester's exact report.
"""

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSaleOrderSeriesInitialDate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Distinct VAT/ref from the module's other test company
        # (test_sale_order_report_layout.py) and skip_automatic_ref so this
        # class's own auto-created company partner never collides with a
        # sibling test class's — both run in the same DB/session, and the
        # ref sequence (a real, non-transactional Postgres sequence) is
        # shared across classes.
        cls.company = (
            cls.env["res.company"]
            .with_context(skip_automatic_ref=True)
            .create(
                {
                    "name": "ARXI PT Series Test Company",
                    "country_id": cls.env.ref("base.pt").id,
                    "currency_id": cls.env.ref("base.EUR").id,
                    "vat": "PT980405319",
                    "entity_type": "S",
                    "commercial_registry": "LISBOA",
                    "company_registry": "980405319",
                    "street": "Rua Teste, 1",
                    "city": "Lisboa",
                    "zip": "1000-001",
                    "l10n_pt_at_test": True,
                    "tax_calculation_rounding_method": "round_globally",
                }
            )
        )
        cls.env.user.write(
            {
                "company_ids": [Command.link(cls.company.id)],
                "company_id": cls.company.id,
            }
        )
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        cls.company = cls.company.with_env(cls.env)
        cls.env["account.chart.template"].try_loading(
            "generic_coa", company=cls.company
        )
        cls.company.account_fiscal_country_id = cls.env.ref("base.pt")

        cls.sale_type = cls.env.ref("l10n_pt_ao_sale.t_quotation")
        cls.journal = cls.env["sale.order.journal"].create(
            {
                "name": "Certified Sale Journal",
                "sale_type_id": cls.sale_type.id,
                "company_id": cls.company.id,
                "l10n_pt_cert": True,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Series Test Customer",
                "country_id": cls.env.ref("base.pt").id,
                "ref": "SERIESCUST1",
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Series Test Product", "type": "service", "lst_price": 50.0}
        )

    def _order(self, name, date_order):
        # A certified journal's create() forces name='/' (the real one is
        # only assigned by the confirm flow's own sequence) — write it
        # directly afterwards to simulate an already-confirmed document
        # without running the whole confirm pipeline.
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sale_journal": self.journal.id,
                "sale_type_id": self.sale_type.id,
                "date_order": date_order,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": self.product.lst_price,
                        }
                    ),
                ],
            }
        )
        order.name = name
        return order

    def test_past_dated_order_blocked_when_no_series_exists_yet(self):
        """No series exists for 2024 in this fresh company — the old code
        auto-created one (stamping today as its initial_date) and let the
        2024-dated document through. Must now be blocked up front, before
        anything is created."""
        order = self._order("OR 2024/0001", "2024-01-15 10:00:00")
        series_count_before = self.env["l10n_pt.account.series"].search_count(
            [("company_id", "=", self.company.id)]
        )
        with self.assertRaises(ValidationError):
            order.get_atcud_for_sale()
        series_count_after = self.env["l10n_pt.account.series"].search_count(
            [("company_id", "=", self.company.id)]
        )
        self.assertEqual(
            series_count_before,
            series_count_after,
            "must not create (and commit) a series before the date is validated",
        )
