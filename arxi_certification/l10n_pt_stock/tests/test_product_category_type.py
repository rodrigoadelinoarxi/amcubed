"""SAF-T product type on categories and the AT inventory file (bloco K).

Pins the 2026-08-24 UAT fix (finding B): a product with no category — or a
category with no SAF-T ``product_type`` — used to come out as "false" in the
AT inventory file, which the tax authority rejects. Now:

  * ``product.category.product_type`` is required (a category can never be
    left without a type),
  * the inventory line generator falls back to 'M' (Goods) when the product
    has no category/type, so the file never carries an empty value.

Deleting a category is deliberately NOT blocked: core sets the products'
categ_id to null (they are not deleted), the 'M' fallback keeps the inventory
file valid, and product.category has no company_id to scope a PT/AO-only guard.
"""

import psycopg2

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestProductCategoryType(TransactionCase):

    def test_product_type_has_default(self):
        """A new category gets 'M' by default, never an empty type."""
        category = self.env["product.category"].create({"name": "Cat default"})
        self.assertEqual(category.product_type, "M")

    @mute_logger("odoo.sql_db")
    def test_product_type_cannot_be_cleared(self):
        """Clearing the SAF-T type is blocked (NOT NULL), so it never ends up
        empty in the inventory file."""
        category = self.env["product.category"].create({"name": "Cat clear"})
        with self.assertRaises(psycopg2.IntegrityError):
            category.product_type = False
            category.flush_recordset()

    def test_inventory_line_falls_back_to_m_without_category(self):
        """The inventory line generator emits 'M', not false, for a product
        with no category."""
        product = self.env["product.product"].create(
            {"name": "No category product", "type": "consu"}
        )
        product.categ_id = False
        wizard = self.env["stock.quantity.history"].create({})
        row = wizard.prepare_quantities_line(5.0, product)
        self.assertEqual(row[0], "M")

    def test_inventory_line_uses_category_type_when_present(self):
        """When the product has a typed category, that type is used as-is."""
        category = self.env["product.category"].create(
            {"name": "Typed cat", "product_type": "P"}
        )
        product = self.env["product.product"].create(
            {"name": "Typed product", "type": "consu", "categ_id": category.id}
        )
        wizard = self.env["stock.quantity.history"].create({})
        row = wizard.prepare_quantities_line(5.0, product)
        self.assertEqual(row[0], "P")
