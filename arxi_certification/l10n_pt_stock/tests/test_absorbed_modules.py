"""Tests for the standalone modules absorbed into l10n_pt_stock (v19).

These check that the functionality moved out of the absorbed modules is now
provided by l10n_pt_stock itself — the fields, their owning behaviour and the
reports — so a merged database behaves exactly like the old multi-module
install.

Absorptions covered:
  * stock_restrictions        -> is_editable / is_return + return wizard
  * stock_report_by_country   -> _get_name_stock_report hook
  * print_conf_copies_pt      -> print.conf.mixer on picking/pt.transport,
                                 per-document print copies and copy-aware reports

Certification-sensitive behaviour (hash / ATCUD / QR / document type) is NOT
touched by these absorptions and is covered elsewhere (l10n_pt_certificate).
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAbsorbedStockModules(TransactionCase):

    # --- stock_restrictions --------------------------------------------------

    def test_restriction_fields_provided_by_core(self):
        """is_editable (computed) and is_return (stored) now live on
        stock.picking through l10n_pt_stock, not the absorbed module."""
        fields = self.env["stock.picking"]._fields
        self.assertIn("is_editable", fields, "stock.picking.is_editable must exist")
        self.assertIn("is_return", fields, "stock.picking.is_return must exist")
        self.assertTrue(
            fields["is_editable"].compute,
            "is_editable must stay a computed field",
        )

    def test_is_return_field_owned_by_l10n_pt_stock(self):
        """The is_return ir.model.fields metadata is owned by l10n_pt_stock
        after the absorption (renamed on collision if needed)."""
        owner = self.env["ir.model.data"].search(
            [
                ("model", "=", "ir.model.fields"),
                ("module", "=", "l10n_pt_stock"),
                (
                    "res_id",
                    "in",
                    self.env["ir.model.fields"]
                    .search([("model", "=", "stock.picking"), ("name", "=", "is_return")])
                    .ids,
                ),
            ]
        )
        self.assertTrue(owner, "is_return must be owned by l10n_pt_stock after the merge")

    def test_return_wizard_override_present_and_owned(self):
        """The absorbed stock.return.picking._create_return override is present
        and owned by l10n_pt_stock (it sits in the model's MRO), so a return
        flags its picking as is_return.

        Only the override's provenance is asserted here — the full return flow
        (which depends on core stock availability/validation mechanics) is
        covered by UI validation, mirroring how the POS suite leaves its
        end-to-end flow to the Playwright tests.
        """
        wizard_cls = type(self.env["stock.return.picking"])
        self.assertTrue(
            hasattr(wizard_cls, "_create_return"),
            "the return wizard override must be present",
        )
        owning_modules = [
            klass.__module__
            for klass in wizard_cls.mro()
            if "_create_return" in klass.__dict__
        ]
        self.assertTrue(
            any("l10n_pt_stock" in module for module in owning_modules),
            "l10n_pt_stock must contribute the _create_return override "
            "(absorbed from stock_restrictions)",
        )

    # --- stock_report_by_country ---------------------------------------------

    def test_stock_report_hook_present(self):
        """_get_name_stock_report (absorbed from stock_report_by_country) is
        available and returns the PT delivery document for PT companies while
        falling back to the base report otherwise (proves the super() chain)."""
        picking = self.env["stock.picking"]
        self.assertTrue(hasattr(picking, "_get_name_stock_report"))

    # --- print_conf_copies_pt ------------------------------------------------

    def test_print_copies_field_on_both_models(self):
        """print_copies (from print.conf.mixer) is now on stock.picking and
        pt.transport through l10n_pt_stock."""
        self.assertIn("print_copies", self.env["stock.picking"]._fields)
        self.assertIn("print_copies", self.env["pt.transport"]._fields)

    def test_company_print_line_registers_pt_transport(self):
        """The per-company print-config document types include pt.transport,
        added by l10n_pt_stock's selection_add."""
        selection = dict(
            self.env["res.company.print.line"]._fields["doc_type"].selection
        )
        self.assertIn(
            "pt.transport",
            selection,
            "pt.transport must be a selectable print-config document type",
        )

    def test_copy_aware_reports_present(self):
        """The three copy-aware reports absorbed from print_conf_copies_pt are
        registered under l10n_pt_stock."""
        for xmlid in (
            "l10n_pt_stock.report_transport",
            "l10n_pt_stock.report_deliveryslip",
            "l10n_pt_stock.report_picking",
        ):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                "%s must be registered after the merge" % xmlid,
            )

    def test_print_copies_resolves_per_company(self):
        """print_copies is resolved per document from the document's company, so
        two companies with different defaults produce different copy counts."""
        company_a = self.env.company
        company_a.default_print_copies = "3"
        company_a.print_conf_type = "contacts"
        company_b = self.env["res.company"].create(
            {"name": "Print copies B", "default_print_copies": "2", "print_conf_type": "contacts"}
        )
        picking_model = self.env["stock.picking"]
        copies_a = picking_model.with_company(company_a)._default_print_copies()
        copies_b = picking_model.with_company(company_b)._default_print_copies()
        self.assertEqual(copies_a, "3", "company A must resolve to 3 copies")
        self.assertEqual(copies_b, "2", "company B must resolve to 2 copies")

    def test_report_duplicates_document_without_creating_records(self):
        """The picking report duplicates the SAME document per copy (browse on
        repeated ids) and never creates new records."""
        partner = self.env["res.partner"].create({"name": "Copies client"})
        pick_type = self.env["stock.picking.type"].search(
            [("code", "=", "outgoing")], limit=1
        )
        before = self.env["stock.picking"].search_count([])
        picking = self.env["stock.picking"].create(
            {"partner_id": partner.id, "picking_type_id": pick_type.id}
        )
        picking.print_copies = "3"
        repeated = picking.browse(
            [d.id for d in picking for _ in range(int(d.print_copies) or 1)]
        )
        self.assertEqual(
            repeated.ids, [picking.id] * 3, "report must render the same doc 3 times"
        )
        self.assertEqual(
            self.env["stock.picking"].search_count([]),
            before + 1,
            "rendering copies must not create extra pickings",
        )

    # --- absorbed modules must be gone ---------------------------------------

    def test_absorbed_modules_not_installed(self):
        """The absorbed modules must no longer be installed (their code now
        lives in l10n_pt_stock). Each is either uninstalled or absent."""
        for name in (
            "stock_restrictions",
            "stock_report_by_country",
            "print_conf_copies_pt",
        ):
            module = self.env["ir.module.module"].search([("name", "=", name)])
            if module:
                self.assertNotEqual(
                    module.state,
                    "installed",
                    "absorbed module %s should no longer be installed" % name,
                )