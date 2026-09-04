"""Regression test for three tax-data gaps found by the Dylan reviewing
``pt_arxi``'s tax CSV (2026-08-25):

1. Several "Gasóleo ... Sujeito a TA (%)" purchase taxes had no
   ``tax_scope`` ("Âmbito do Imposto") set — should be "service" like
   their 0%/8% siblings.
2. "IVA 0% Autoliquidação - M40 Extracomunitário" was archived by default
   and had no fiscal-position mapping — its sibling "...M40
   Intracomunitário" already had both.
3. The "(Bens)" regional sale taxes (Açores/Madeira) had no
   fiscal-position mapping at all, unlike their "(Serviços)" siblings,
   which are fully mapped — a systemic gap across both regions, not just
   the one Madeira 4% case reported.
"""
from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPtArxiTaxFiscalPositionMapping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "ARXI PT Tax Mapping Test Company",
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
            "pt_arxi", company=cls.company
        )

    def _tax(self, name, region="PT", type_tax_use="sale"):
        tax = self.env["account.tax"].search(
            [
                ("name", "=", name),
                ("company_id", "=", self.company.id),
                ("country_region", "=", region),
                ("type_tax_use", "=", type_tax_use),
            ],
            limit=1,
        )
        self.assertTrue(tax, f"Tax not found: {name} ({region}, {type_tax_use})")
        return tax

    def _fiscal_position(self, name):
        fp = self.env["account.fiscal.position"].search(
            [("name", "=", name), ("company_id", "=", self.company.id)], limit=1
        )
        self.assertTrue(fp, f"Fiscal position not found: {name}")
        return fp

    def test_gasoleo_purchase_taxes_have_service_scope(self):
        """All "Sujeito a TA (%)" fuel taxes must be tax_scope='service',
        not just the 0%/8% ones."""
        taxes = self.env["account.tax"].search(
            [
                ("company_id", "=", self.company.id),
                ("name", "like", "Gasóleo"),
                ("type_tax_use", "=", "purchase"),
            ]
        )
        self.assertGreaterEqual(len(taxes), 12)
        for tax in taxes:
            self.assertEqual(
                tax.tax_scope,
                "service",
                f"{tax.name} should be tax_scope='service'",
            )

    def test_m40_extracomunitario_active_and_mapped(self):
        """The Extracomunitário M40 tax must be active and replace the
        three mainland service taxes under the Extra-Community fiscal
        position — mirroring the already-correct Intracomunitário sibling."""
        m40_extra = self.env["account.tax"].search(
            [
                ("name", "=", "IVA 0% Autoliquidação - M40 Extracomunitário"),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        self.assertTrue(m40_extra)
        self.assertTrue(m40_extra.active)

        fp_extra = self._fiscal_position("Extra-Community")
        self.assertIn(fp_extra, m40_extra.fiscal_position_ids)

        for name in (
            "IVA 23% (Serviços)",
            "IVA 13% (Serviços)",
            "IVA 6% (Serviços)",
        ):
            src_tax = self._tax(name)
            self.assertIn(
                m40_extra,
                fp_extra.map_tax(src_tax),
                f"{name} should map to M40 Extracomunitário under Extra-Community",
            )

    def test_regional_goods_taxes_mapped_like_their_service_siblings(self):
        """Every regional (Açores/Madeira) '(Bens)' sale tax must have the
        same kind of fiscal-position mapping its '(Serviços)' sibling
        already has — this was completely missing for all six."""
        cases = [
            ("Azores", "IVA 6% (Bens)", "IVA 4% (Bens)", "PT-AC"),
            ("Azores", "IVA 13% (Bens)", "IVA 9% (Bens)", "PT-AC"),
            ("Azores", "IVA 23% (Bens)", "IVA 16% (Bens)", "PT-AC"),
            ("Madeira", "IVA 6% (Bens)", "IVA 4% (Bens)", "PT-MA"),
            ("Madeira", "IVA 13% (Bens)", "IVA 12% (Bens)", "PT-MA"),
            ("Madeira", "IVA 23% (Bens)", "IVA 22% (Bens)", "PT-MA"),
        ]
        for fp_name, mainland_name, regional_name, region in cases:
            fp = self._fiscal_position(fp_name)
            mainland_tax = self._tax(mainland_name)
            regional_tax = self._tax(regional_name, region=region)
            self.assertIn(fp, regional_tax.fiscal_position_ids)
            self.assertIn(
                regional_tax,
                fp.map_tax(mainland_tax),
                f"{mainland_name} should map to {regional_name} under {fp_name}",
            )
