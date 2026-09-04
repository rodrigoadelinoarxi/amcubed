"""UAT vendas/stock, ponto 13 follow-up (2026-08-27): the "Create AT
Transport Document" button on a picking must respect the company's
``at_foreign_partners`` setting, not just hard-require a PT partner.

Before this fix, ``is_pt_internal_deliverable`` ignored the setting
entirely: the button never showed for a foreign contact even when
``at_foreign_partners`` was enabled — the exact scenario the UAT tester
(Paulo) hit ("não deixa, pois nem aparece na lista").
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTransportButtonVisibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {"name": "PT Transport Co", "country_id": cls.env.ref("base.pt").id}
        )
        cls.pt_partner = cls.env["res.partner"].create(
            {"name": "PT Partner", "country_id": cls.env.ref("base.pt").id}
        )
        cls.foreign_partner = cls.env["res.partner"].create(
            {"name": "ES Partner", "country_id": cls.env.ref("base.es").id}
        )
        cls.pick_type = cls.env["stock.picking.type"].search(
            [("code", "=", "outgoing"), ("company_id", "in", (cls.company.id, False))],
            limit=1,
        )

    def _picking(self, partner):
        return self.env["stock.picking"].create(
            {
                "partner_id": partner.id,
                "picking_type_id": self.pick_type.id,
                "company_id": self.company.id,
            }
        )

    def test_pt_partner_always_eligible(self):
        self.company.at_foreign_partners = False
        picking = self._picking(self.pt_partner)
        self.assertTrue(picking.is_pt_internal_deliverable)

    def test_foreign_partner_blocked_when_setting_disabled(self):
        self.company.at_foreign_partners = False
        picking = self._picking(self.foreign_partner)
        self.assertFalse(picking.is_pt_internal_deliverable)

    def test_foreign_partner_eligible_when_setting_enabled(self):
        self.company.at_foreign_partners = True
        picking = self._picking(self.foreign_partner)
        self.assertTrue(picking.is_pt_internal_deliverable)

    def test_non_pt_company_never_eligible(self):
        """The company itself must still be PT — a foreign company is
        never eligible regardless of the partner or the setting."""
        other_company = self.env["res.company"].create(
            {"name": "Non-PT Co", "country_id": self.env.ref("base.es").id}
        )
        other_company.at_foreign_partners = True
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.foreign_partner.id,
                "picking_type_id": self.pick_type.id,
                "company_id": other_company.id,
            }
        )
        self.assertFalse(picking.is_pt_internal_deliverable)
