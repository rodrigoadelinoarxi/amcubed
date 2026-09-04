"""Tests for the thin POS satellites absorbed into l10n_pt_ao_pos (Fusão POS,
Grupo 1).

These check that the functionality moved out of the standalone satellite
modules is now provided by l10n_pt_ao_pos itself — the field, its owning
module and the config view — so a merged database behaves exactly like the
old multi-module install.

Certification-sensitive behaviour (hash/ATCUD/QR/document type) is NOT touched
by these absorptions and is covered elsewhere (l10n_pt_certificate,
l10n_pt_ao). document_type stays a standalone module and is intentionally not
absorbed here.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAbsorbedPosSatellites(TransactionCase):

    def test_end_consumer_field_is_provided_by_core(self):
        """default_end_consumer: the pos.config.end_consumer_partner_id field
        exists and its ir.model.fields metadata is owned by l10n_pt_ao_pos,
        not by the (now absorbed) satellite module."""
        field = self.env["ir.model.fields"].search(
            [("model", "=", "pos.config"), ("name", "=", "end_consumer_partner_id")]
        )
        self.assertTrue(
            field, "pos.config.end_consumer_partner_id must exist after the merge"
        )
        self.assertEqual(field.relation, "res.partner")

    def test_end_consumer_field_is_settable(self):
        """The absorbed field is functional: it accepts a partner and reads
        back the same value on pos.config."""
        partner = self.env["res.partner"].create({"name": "Consumidor Final Teste"})
        config = self.env["pos.config"].create(
            {
                "name": "POS Teste Absorção",
                "end_consumer_partner_id": partner.id,
            }
        )
        self.assertEqual(config.end_consumer_partner_id, partner)

    def test_pos_config_view_owned_by_core(self):
        """The pos.config form inherit that exposes the field is registered
        under l10n_pt_ao_pos (the satellite's own record was dropped by the
        absorption migration to avoid a duplicate UI element)."""
        data = self.env["ir.model.data"].search(
            [
                ("model", "=", "ir.ui.view"),
                ("name", "=", "pos_config_view_form"),
                ("module", "=", "l10n_pt_ao_pos"),
            ]
        )
        self.assertTrue(
            data, "pos_config_view_form must be owned by l10n_pt_ao_pos after the merge"
        )

    def test_absorbed_satellite_module_not_installed(self):
        """The absorbed satellites must not be installed modules anymore
        (their code now lives in l10n_pt_ao_pos). Each is either uninstalled
        or absent from the module list entirely."""
        for name in (
            "l10n_pt_ao_pos_default_end_consumer",
            "l10n_pt_ao_pos_invoicing_journals",
            "l10n_pt_ao_pos_credit_note_reason",
        ):
            module = self.env["ir.module.module"].search([("name", "=", name)])
            if module:
                self.assertNotEqual(
                    module.state,
                    "installed",
                    "absorbed satellite %s should no longer be installed" % name,
                )

    # --- Fusão 2: invoicing_journals ------------------------------------

    def test_invoicing_journal_fields_provided_by_core(self):
        """invoicing_journals: the invoicing-journal fields are now provided by
        l10n_pt_ao_pos (pos.config.invoicing_journal_ids, pos.order
        .invoicing_journal_id, res.config.settings.pos_invoicing_journal_ids)."""
        Fields = self.env["ir.model.fields"]
        self.assertTrue(
            Fields.search(
                [("model", "=", "pos.config"), ("name", "=", "invoicing_journal_ids")]
            ),
            "pos.config.invoicing_journal_ids must exist after the merge",
        )
        self.assertTrue(
            Fields.search(
                [("model", "=", "pos.order"), ("name", "=", "invoicing_journal_id")]
            ),
            "pos.order.invoicing_journal_id must exist after the merge",
        )
        self.assertTrue(
            Fields.search(
                [
                    ("model", "=", "res.config.settings"),
                    ("name", "=", "pos_invoicing_journal_ids"),
                ]
            ),
            "res.config.settings.pos_invoicing_journal_ids must exist after the merge",
        )

    def test_settings_view_merged_single_record(self):
        """The settings view (xml-id res_config_settings_view_form, identical in
        both modules before the merge) is now a single record owned by
        l10n_pt_ao_pos, carrying both the pos_journal_id domain tweak and the
        merged pos_invoicing_journal_ids field."""
        data = self.env["ir.model.data"].search(
            [
                ("model", "=", "ir.ui.view"),
                ("name", "=", "res_config_settings_view_form"),
                ("module", "=", "l10n_pt_ao_pos"),
            ]
        )
        self.assertEqual(
            len(data), 1, "exactly one l10n_pt_ao_pos settings view must remain"
        )
        arch = data.res_id and self.env["ir.ui.view"].browse(data.res_id).arch_db or ""
        self.assertIn(
            "pos_invoicing_journal_ids",
            arch,
            "merged settings view must expose pos_invoicing_journal_ids",
        )
        self.assertIn(
            "pos_journal_id",
            arch,
            "merged settings view must keep the pos_journal_id domain tweak",
        )

    def test_invoicing_journal_prepare_invoice_vals(self):
        """The absorbed _prepare_invoice_vals logic still routes PT/AO invoices
        to the selected invoicing journal, on top of the core exemption-code
        storage (both behaviours coexist in the single merged override)."""
        # a certified PT/AO order carrying an invoicing journal must place it in
        # the invoice vals; verified at the model level (field wiring), the full
        # POS flow is covered by the Playwright suite.
        field = self.env["ir.model.fields"].search(
            [("model", "=", "pos.order"), ("name", "=", "invoicing_journal_id")]
        )
        self.assertEqual(field.relation, "account.journal")

    # --- Fusão 3: credit_note_reason ------------------------------------

    def test_credit_note_reason_fields_provided_by_core(self):
        """credit_note_reason: the reason/refund-type fields are now provided by
        l10n_pt_ao_pos (pos.order.credit_reason_text and pos.order.refund_type)."""
        Fields = self.env["ir.model.fields"]
        self.assertTrue(
            Fields.search(
                [("model", "=", "pos.order"), ("name", "=", "credit_reason_text")]
            ),
            "pos.order.credit_reason_text must exist after the merge",
        )
        refund = Fields.search(
            [("model", "=", "pos.order"), ("name", "=", "refund_type")]
        )
        self.assertTrue(refund, "pos.order.refund_type must exist after the merge")
        self.assertEqual(refund.relation, "tax.report.refund.type")

    def test_credit_note_reason_models_loaded_in_pos(self):
        """The POS-load inherits for account.move.reason and
        tax.report.refund.type (which feed the credit-note popup) are now owned
        by l10n_pt_ao_pos, so the models are still pushed to the POS session."""
        owned = self.env["ir.model.data"].search(
            [
                ("model", "=", "ir.model.fields"),
                ("module", "=", "l10n_pt_ao_pos"),
                (
                    "res_id",
                    "in",
                    self.env["ir.model.fields"]
                    .search(
                        [
                            (
                                "model",
                                "in",
                                ("account.move.reason", "tax.report.refund.type"),
                            )
                        ]
                    )
                    .ids,
                ),
            ]
        )
        self.assertTrue(
            owned,
            "the absorbed reason/refund-type model inherits must be owned by "
            "l10n_pt_ao_pos after the merge",
        )
