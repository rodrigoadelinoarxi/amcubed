"""Regression test (PQC 2026-08): the very first POS order of a session
could fail to invoice with "Expected singleton: account.document.type(...)"
when more than one ``account.document.type`` shared the same code across
companies/countries — ``_prepare_invoice_vals()`` searched by ``code``
alone, with no country scoping and no ``limit=1``.
"""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDocumentTypeLookup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pt_company = cls.env["res.company"].create(
            {"name": "PQC PT Company", "country_id": cls.env.ref("base.pt").id}
        )
        cls.ao_company = cls.env["res.company"].create(
            {"name": "PQC AO Company", "country_id": cls.env.ref("base.ao").id}
        )
        # A second "FT"/PT type, bypassing the model's own (code, country_id)
        # uniqueness intent via force_write — reproducing, at the data
        # level, the exact situation the reported traceback names: more
        # than one account.document.type record matching the same code
        # (there it was three: ids 1, 19, 20).
        cls.doc_type_ao = cls.env["account.document.type"].search(
            [("code", "=", "FT"), ("country_id", "=", cls.env.ref("base.ao").id)],
            limit=1,
        ) or cls.env["account.document.type"].create(
            {
                "name": "Fatura AO",
                "code": "FT",
                "country_id": cls.env.ref("base.ao").id,
                "category": "invoicing",
            }
        )
        cls.env["account.document.type"].create(
            {
                "name": "Fatura PT Duplicada",
                "code": "FT",
                "country_id": cls.env.ref("base.pt").id,
                "category": "invoicing",
            }
        )

    def test_lookup_does_not_crash_with_duplicate_codes_for_the_same_country(self):
        """The actual reported crash: more than one account.document.type
        row matches the same code — must return exactly one, not raise
        "Expected singleton"."""
        order = self.env["pos.order"].new({"company_id": self.pt_company.id})
        found = order._pt_arxi_find_document_type("FT")
        self.assertEqual(len(found), 1)
        self.assertEqual(found.country_id, self.env.ref("base.pt"))

    def test_lookup_scopes_by_country(self):
        pt_order = self.env["pos.order"].new({"company_id": self.pt_company.id})
        ao_order = self.env["pos.order"].new({"company_id": self.ao_company.id})
        self.assertEqual(
            pt_order._pt_arxi_find_document_type("FT").country_id,
            self.env.ref("base.pt"),
        )
        self.assertEqual(
            ao_order._pt_arxi_find_document_type("FT"), self.doc_type_ao
        )

    def test_lookup_returns_empty_for_unknown_code(self):
        order = self.env["pos.order"].new({"company_id": self.pt_company.id})
        self.assertFalse(order._pt_arxi_find_document_type("NOPE"))
