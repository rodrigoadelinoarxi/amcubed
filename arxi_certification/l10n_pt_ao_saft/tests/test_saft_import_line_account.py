"""Regression test for the 2026-08-24 fix (UAT 42d): an imported SAF-T
invoice line's income account must be resolved through the partner's
fiscal position (same as manually creating an invoice does), not always
the product's own ``property_account_income_id`` — an extra-EU/extra-country
customer needs the mapped export account, not the domestic default.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_pt_ao.tests.test_l10n_pt_ao_common import (
    AccountTestCertifiedCommon,
)


@tagged("post_install", "-at_install")
class TestSaftImportLineAccount(AccountTestCertifiedCommon):

    def test_line_account_uses_fiscal_position_mapping(self):
        default_account = self.env["account.account"].create(
            {
                "name": "Domestic Sales Test",
                "code": "DOMESTICTEST",
                "account_type": "income",
                "company_ids": [(6, 0, self.company.ids)],
            }
        )
        self.product.property_account_income_id = default_account
        export_account = self.env["account.account"].create(
            {
                "name": "Export Sales Test",
                "code": "EXPORTTEST",
                "account_type": "income",
                "company_ids": [(6, 0, self.company.ids)],
            }
        )

        foreign_partner = self.env["res.partner"].create(
            {
                "name": "US Customer",
                "country_id": self.env.ref("base.us").id,
                "company_id": False,
            }
        )
        fiscal_position = self.env["account.fiscal.position"].create(
            {
                "name": "Extra-EU Export Test",
                "company_id": self.company.id,
                "auto_apply": True,
                "country_id": self.env.ref("base.us").id,
                "account_ids": [
                    Command.create(
                        {
                            "account_src_id": default_account.id,
                            "account_dest_id": export_account.id,
                        }
                    )
                ],
            }
        )
        self.assertEqual(
            self.env["account.fiscal.position"]._get_fiscal_position(
                foreign_partner
            ),
            fiscal_position,
        )

        wiz_customer = self.env["saft.import.wizard.customer"].create(
            {
                "partner_id": foreign_partner.id,
                "ref": "CUSTUS1",
                "name": foreign_partner.name,
                "country_id": foreign_partner.country_id.id,
            }
        )
        wiz_product = self.env["saft.import.wizard.product"].create(
            {
                "product_id": self.product.id,
                "default_code": self.product.default_code or "PRODX",
                "name": self.product.name,
            }
        )
        wiz_tax = self.env["saft.import.wizard.tax"].create(
            {
                "name": self.tax_sale.name,
                "amount": self.tax_sale.amount,
                "amount_type": "percent",
                "company_id": self.company.id,
            }
        )
        wiz_invoice = self.env["saft.import.wizard.invoice"].create(
            {"partner_id": wiz_customer.id}
        )
        wiz_line = self.env["saft.import.wizard.invoice.line"].create(
            {
                "invoice_id": wiz_invoice.id,
                "name": "Test line",
                "price_unit": 100.0,
                "quantity": 1.0,
                "origin": "",
                "product_id": wiz_product.id,
                "tax_id": wiz_tax.id,
            }
        )

        result = wiz_line.prepare_base_invoice_lines()
        self.assertEqual(result[0]["account_id"], export_account.id)
