"""Regression tests for the 2026-08-24 fix (UAT 13/13b): partner VAT/ref
uniqueness (exact match only — a trailing space is a different string, same
decision as UAT 12) and self-billing required fields enforced on every
save, not just via the UI onchange. All checks are gated to PT/AO
companies — a non-PT/AO company must never be blocked by any of this.
"""

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestPartnerReference(AccountTestCertifiedCommon):

    def _partner(self, **kwargs):
        vals = {"name": "Test Partner", "company_id": self.company.id}
        vals.update(kwargs)
        return self.env["res.partner"].create(vals)

    def test_ref_duplicate_blocked(self):
        self._partner(ref="REF001")
        with self.assertRaises(ValidationError):
            self._partner(ref="REF001", name="Other")

    def test_ref_trailing_space_not_duplicate(self):
        self._partner(ref="REF002")
        p2 = self._partner(ref="REF002 ", name="Other")
        self.assertEqual(p2.ref, "REF002 ")

    def test_ref_emoji_blocked(self):
        """UAT vendas/stock follow-up (2026-08-27): reported live — an
        emoji in the customer reference saved without error, same class
        of bug as UAT 12's product default_code (no charset check on
        ref at all, unlike default_code's own
        _check_default_code_charset)."""
        with self.assertRaises(ValidationError):
            self._partner(ref="REF\U0001F600")

    def test_ref_accented_char_allowed(self):
        """Windows-1252 covers accented PT characters — must not be
        rejected, same decision as the product reference check."""
        p = self._partner(ref="REFÇÃO")
        self.assertEqual(p.ref, "REFÇÃO")

    def test_ref_not_copied_on_duplicate(self):
        """Dylan (2026-08-27): copy=False on ref (mirrors product.product's
        default_code) avoids the collision at the source — duplicating a
        contact used to carry over the same ref, only to be rejected by
        _check_ref_unique the moment the duplicate was saved. Not copying
        it means the copy never starts out as an actual duplicate:
        create()'s own automatic-mode auto-fill (unrelated to this fix,
        same mechanism as the product reference's) gives it a fresh one
        instead of leaving it blank, since Automatic is this env's
        default mode."""
        p1 = self._partner(ref="REF003")
        p2 = p1.copy()
        self.assertTrue(p2.ref)
        self.assertNotEqual(p2.ref, "REF003")

    def test_ref_not_copied_stays_blank_in_manual_mode(self):
        """Same fix, Manual mode: no auto-fill applies, so the copy simply
        starts with an empty ref instead of the original's — prompting
        for a real new one, rather than silently duplicating it."""
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.partner_ref_type", "0"
        )
        p1 = self._partner(ref="REF004")
        p2 = p1.copy()
        self.assertFalse(p2.ref)

    def test_vat_duplicate_blocked_top_level(self):
        self._partner(vat="PT123456789")
        with self.assertRaises(ValidationError):
            self._partner(vat="PT123456789", name="Other")

    def test_vat_shared_between_parent_and_child_allowed(self):
        parent = self._partner(vat="PT987654321")
        # A child contact legitimately shares the parent's VAT.
        child = self.env["res.partner"].create(
            {
                "name": "Contact person",
                "parent_id": parent.id,
                "vat": "PT987654321",
                "company_id": self.company.id,
            }
        )
        self.assertEqual(child.vat, parent.vat)

    def test_final_consumer_vat_exempt_from_uniqueness(self):
        self._partner(vat="999999999")
        # A second partner with the same final-consumer VAT must not raise.
        p2 = self._partner(vat="999999999", name="Other final consumer")
        self.assertEqual(p2.vat, "999999999")

    def test_self_billing_required_fields_enforced_on_write(self):
        """UAT 13b: erasing a required field via a direct write() after
        allows_self_billing is already True must be blocked, not just
        warned about in the UI onchange."""
        partner = self._partner(
            vat="PT123456789",
            street="Rua Teste",
            city="Lisboa",
            country_id=self.env.ref("base.pt").id,
            allows_self_billing=True,
        )
        with self.assertRaises(ValidationError):
            partner.write({"street": False})

    def test_non_pt_ao_company_not_affected_by_any_check(self):
        """A non-PT/AO company must never be blocked by the product/partner
        reference rules added for PT/AO."""
        other_company = self.env["res.company"].create(
            {"name": "Non PT/AO Co", "country_id": self.env.ref("base.us").id}
        )
        self.env["res.partner"].create(
            {"name": "US Partner 1", "vat": "US123", "company_id": other_company.id}
        )
        # Same VAT, same non-PT/AO company: must not raise.
        p2 = self.env["res.partner"].create(
            {"name": "US Partner 2", "vat": "US123", "company_id": other_company.id}
        )
        self.assertEqual(p2.vat, "US123")

        # Must not raise: creating a product without an explicit reference
        # is never forced to fail for a non-PT/AO company, whichever the
        # automatic/manual generation mode is.
        self.env["product.product"].create(
            {"name": "US product", "type": "service", "company_id": other_company.id}
        )
