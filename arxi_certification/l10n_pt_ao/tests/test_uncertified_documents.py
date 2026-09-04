from odoo.tests import tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestUncertifiedDocuments(AccountTestCertifiedCommon):
    """Non-certified (l10n_cert=False) journals: none of the PT/AO
    certification rules should apply — behaviour must match stock Odoo.

    A regular (non-'P' source_billing) uncertified journal falls outside all
    of the certification hooks (they gate on ``journal_id.l10n_cert``), so
    these tests are really pinning that behaviour, not exercising new logic.
    """

    def test_negative_quantity_line_allowed(self):
        """A negative-quantity line (e.g. a correction line) is a standard
        Odoo feature and must not be blocked by our code outside certified
        journals — only ``_pt_arxi_check_negative_lines`` (gated on
        ``l10n_cert``) forbids it, and that hook never runs here.

        Note: a genuinely negative *total* invoice is rejected by native
        Odoo itself (account/models/account_move.py), regardless of any
        l10n_pt_ao code — not something this suite should (or could) assert
        as "allowed"."""
        move = self._create_invoice_with_negative_line(self.uncertified_sale_journal)
        move.action_post()

        self.assertEqual(move.state, "posted")

    def test_product_without_internal_reference_does_not_block_posting(self):
        """Stock Odoo doesn't require an internal reference to invoice a product."""
        move = self._create_invoice(
            self.uncertified_sale_journal, product=self.product_no_ref
        )
        move.action_post()

        self.assertEqual(move.state, "posted")

    def test_partner_without_reference_does_not_block_posting(self):
        """Stock Odoo doesn't require a partner reference to invoice them."""
        move = self._create_invoice(
            self.uncertified_sale_journal, partner=self.partner_no_ref
        )
        move.action_post()

        self.assertEqual(move.state, "posted")

    def test_partner_and_product_not_locked_by_posting(self):
        """Posting an uncertified document must not freeze the partner/product
        (that lock is a certified-document-only side effect)."""
        move = self._create_invoice(self.uncertified_sale_journal)
        move.action_post()

        self.assertNotEqual(self.partner.state, "locked")
        self.assertNotEqual(self.product.state, "locked")

    def test_posted_document_can_reset_to_draft(self):
        """An uncertified document keeps the native reset-to-draft behaviour
        (no certification lock applies)."""
        move = self._create_invoice(self.uncertified_sale_journal)
        move.action_post()

        move.button_draft()

        self.assertEqual(move.state, "draft")

    def test_credit_note_without_origin_allowed(self):
        """Outside certified journals, a credit note doesn't need to link
        back to an original invoice line — standard Odoo behaviour.

        Decision 2026-07-15: confirmed the traceability requirement in
        ``_pt_arxi_check_credit_note_origin`` is an AT-certification
        concern, not a PT/AO-wide legal one — the check is now gated on
        ``journal_id.l10n_cert`` like every other check in this suite."""
        move = self._create_invoice(self.uncertified_sale_journal)
        move.action_post()

        credit_note = self._create_invoice(
            self.uncertified_sale_journal, partner=self.partner
        )
        credit_note.move_type = "out_refund"
        credit_note.action_post()

        self.assertEqual(credit_note.state, "posted")
