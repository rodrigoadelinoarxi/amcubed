from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSaleOrderReportLayout(TransactionCase):
    """``sale.order._get_name_sale_report()`` must pick the Arxi/PT layout
    only for actually certified sale orders (certified sale journal), not
    just any PT company — see ponto 1 of ``pdfs-certificados-plano.md``.
    First test suite for this module (none existed before)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "ARXI PT Sale Test Company",
                "country_id": cls.env.ref("base.pt").id,
                "currency_id": cls.env.ref("base.EUR").id,
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

        sale_type = cls.env.ref("l10n_pt_ao_sale.t_order")
        cls.certified_journal = cls.env["sale.order.journal"].create(
            {
                "name": "Certified Sale Journal",
                "sale_type_id": sale_type.id,
                "company_id": cls.company.id,
                "l10n_pt_cert": True,
            }
        )
        cls.uncertified_journal = cls.env["sale.order.journal"].create(
            {
                "name": "Uncertified Sale Journal",
                "sale_type_id": sale_type.id,
                "company_id": cls.company.id,
                "l10n_pt_cert": False,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Sale Test Customer",
                "country_id": cls.env.ref("base.pt").id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Sale Test Product", "type": "service", "lst_price": 50.0}
        )

    def _create_order(self, journal):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "sale_journal": journal.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                        }
                    )
                ],
            }
        )

    def test_certified_sale_order_uses_arxi_layout(self):
        order = self._create_order(self.certified_journal)
        self.assertEqual(
            order._get_name_sale_report(), "l10n_pt_sale.report_saleorder_document"
        )

    def test_uncertified_sale_order_uses_native_layout(self):
        order = self._create_order(self.uncertified_journal)
        self.assertNotEqual(
            order._get_name_sale_report(), "l10n_pt_sale.report_saleorder_document"
        )
