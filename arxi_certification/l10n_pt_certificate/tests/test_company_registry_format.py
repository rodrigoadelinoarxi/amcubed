"""Regression test: a PT company's ``company_registry``/``commercial_registry``
format is validated on ``create()`` too, not only on a later ``write()``.

Before this fix, creating a company through the normal "New Company" form
(a single ``create()``) with ``company_registry`` set to free text (e.g. the
conservatória name instead of the 9-digit registration number) went through
untouched — the format check only ran inside ``write()``. The bad value then
silently produced an invalid SAF-T ``CompanyID`` (e.g. "Alcobaça Alcobaça"
instead of "LISBOA 509445923"), surfacing only months later as a cryptic XSD
pattern-mismatch error at export time.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCompanyRegistryFormat(TransactionCase):

    def _company_vals(self, **overrides):
        vals = {
            "name": "Registry Format Test Company",
            "country_id": self.env.ref("base.pt").id,
            "vat": "PT123456789",
            "entity_type": "S",
            "commercial_registry": "LISBOA",
            "company_registry": "123456789",
            "street": "Rua Teste, 1",
            "city": "Lisboa",
            "zip": "1000-001",
        }
        vals.update(overrides)
        return vals

    def test_create_rejects_free_text_company_registry(self):
        """The exact bug: 'Alcobaça' (a place name) instead of a 9-digit
        registration number must be rejected at creation."""
        with self.assertRaises(ValidationError):
            self.env["res.company"].create(
                self._company_vals(company_registry="Alcobaça")
            )

    def test_create_rejects_invalid_commercial_registry(self):
        with self.assertRaises(ValidationError):
            self.env["res.company"].create(
                self._company_vals(commercial_registry="Alcobaça123")
            )

    def test_create_accepts_valid_registries(self):
        company = self.env["res.company"].create(self._company_vals())
        self.assertEqual(company.company_registry, "123456789")

    def test_create_does_not_validate_non_pt_company(self):
        """A non-PT company isn't subject to this format check at all."""
        company = self.env["res.company"].create(
            self._company_vals(
                country_id=self.env.ref("base.us").id,
                company_registry="not-a-nif-at-all",
            )
        )
        self.assertEqual(company.company_registry, "not-a-nif-at-all")
