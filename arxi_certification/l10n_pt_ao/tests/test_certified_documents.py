from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestCertifiedDocuments(AccountTestCertifiedCommon):
    """Certified (l10n_cert=True) sale documents: the general PT/AO
    certification rules (data requirements, negative-line/total blocks,
    partner/product locking, credit-note traceability) — country-agnostic,
    as opposed to the AT-specific field generation (hash/ATCUD/QR) tested in
    ``l10n_pt_certificate``."""

    def test_negative_quantity_forbidden_on_certified_journal(self):
        """AT/AGT forbids negative-quantity lines on certified sale documents,
        even when the overall total stays positive (isolates our
        ``_pt_arxi_check_negative_lines`` from native Odoo's separate
        negative-*total* block)."""
        move = self._create_invoice_with_negative_line(self.sale_journal)

        with self.assertRaises(UserError):
            move.action_post()

    def test_negative_total_forbidden_on_certified_journal(self):
        """A negative document total on certified sale documents is
        forbidden."""
        move = self._create_invoice(self.sale_journal, price_unit=-100.0)

        with self.assertRaises(UserError):
            move.action_post()

    def test_negative_unit_price_allowed_on_certified_journal(self):
        """Negative unit price alone (e.g. a manual discount line) is
        allowed on certified sale documents — only negative *quantity* and
        a negative document *total* are forbidden."""
        move = self._create_invoice_with_negative_price_line(self.sale_journal)

        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_product_without_internal_reference_blocks_posting(self):
        """Products on certified documents must have an internal reference
        (SAF-T ProductCode)."""
        move = self._create_invoice(self.sale_journal, product=self.product_no_ref)

        with self.assertRaises(UserError):
            move.action_post()

    def test_partner_without_reference_blocks_posting(self):
        """The customer on a certified document must have a reference
        (SAF-T CustomerID)."""
        move = self._create_invoice(self.sale_journal, partner=self.partner_no_ref)

        with self.assertRaises(UserError):
            move.action_post()

    def test_certified_document_locks_partner_and_product(self):
        """Posting a certified document freezes (locks) the partner and the
        products used on it."""
        move = self._create_invoice(self.sale_journal)
        self.assertNotEqual(self.partner.state, "locked")
        self.assertNotEqual(self.product.state, "locked")

        move.action_post()

        self.assertEqual(self.partner.state, "locked")
        self.assertEqual(self.product.state, "locked")

    def test_credit_note_without_origin_blocked(self):
        """A certified credit note line without a link to the original
        invoice line is rejected."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()

        credit_note = self._create_invoice(self.sale_journal, partner=self.partner)
        credit_note.move_type = "out_refund"

        with self.assertRaises(UserError):
            credit_note.action_post()

    def test_confirmed_document_header_fields_blocked(self):
        """Once posted, native Odoo's own hash lock (triggered by
        ``restrict_mode_hash_table``, independent of our PT-specific
        ``pt_arxi_inalterable_hash``) forbids editing the fields the
        integrity hash is computed from: ``name``, ``date``, ``journal_id``,
        ``company_id`` (see ``account.move._get_integrity_hash_fields``)."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()
        self.assertTrue(move.inalterable_hash)

        with self.assertRaises(UserError):
            move.write({"date": fields.Date.today() - timedelta(days=1)})
        with self.assertRaises(UserError):
            move.write({"name": "FT SOMETHING/9999"})

    def test_confirmed_document_value_fields_blocked(self):
        """Native Odoo's hash-integrity write guard only covers
        ``name``/``date``/``journal_id``/``company_id`` — it doesn't cover
        the customer or the line values. ``_pt_arxi_check_certified_value_
        fields_locked`` (account.move) and the ``account.move.line`` write
        override extend the same lock to ``partner_id`` and line
        product/quantity/price_unit/discount once the document is hashed,
        for PT/AO companies only (``account_id`` is deliberately left
        editable — an internal bookkeeping correction, not AT-certified
        data)."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()
        self.assertTrue(move.inalterable_hash)

        other_partner = self.env["res.partner"].create(
            {"name": "Another Partner", "ref": "CUST002"}
        )
        with self.assertRaises(ValidationError):
            move.write({"partner_id": other_partner.id})

        with self.assertRaises(ValidationError):
            move.invoice_line_ids.write({"price_unit": 999.0})

    def test_confirmed_document_account_id_still_blocked_by_native_odoo(self):
        """``account_id`` is deliberately left out of this module's own
        ``LOCKED_LINE_FIELDS`` (it's an internal bookkeeping classification,
        not AT-certified data) — but native Odoo's own line-level
        hash-integrity guard (``account.move.line._get_integrity_hash_
        fields``: name/debit/credit/account_id/partner_id) blocks it
        regardless, unconditionally, with no bypass. So it stays blocked in
        practice — this pins that as the real, current behaviour rather
        than assuming our own field list is the only thing protecting it."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()
        self.assertTrue(move.inalterable_hash)

        other_account = self.env["account.account"].create(
            {
                "name": "Alternative Income Account",
                "code": "700100",
                "account_type": "income",
            }
        )
        with self.assertRaises(UserError):
            move.invoice_line_ids.write({"account_id": other_account.id})

    def test_confirmed_document_partner_id_stays_blocked_even_with_force_write(self):
        """``force_write`` bypasses our own header-level check *and*
        cascades to native Odoo's ``skip_readonly_check`` (its "readonly
        fields on a posted move" guard) — but changing ``partner_id`` also
        triggers native's ``_inverse_partner_id``, which propagates the new
        commercial partner onto every line via a plain ``write()``. That
        line-level write hits native Odoo's *unconditional, no-bypass*
        hash-integrity guard (the same one that blocks ``account_id`` —
        ``partner_id`` is in the same protected field list on
        ``account.move.line``). So the customer of a hashed document can't
        actually be changed by any means short of clearing the hash first —
        this is a hard architectural wall in native Odoo, not a gap in our
        own checks."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()

        other_partner = self.env["res.partner"].create(
            {"name": "Another Partner", "ref": "CUST002"}
        )
        with self.assertRaises(UserError):
            move.with_context(force_write=True).write({"partner_id": other_partner.id})

    def test_cancelled_document_fields_still_blocked(self):
        """The hash lock survives cancellation: a certified document keeps
        its ``inalterable_hash`` when moved to 'cancel' (via this module's
        ``button_cancel`` override, which cancels in place instead of
        resetting to draft first), so the same protected fields — header
        and value alike — stay blocked."""
        reason = self.env["account.move.reason"].create(
            {"name": "Test cancel reason", "reason_type": "cancel"}
        )
        move = self._create_invoice(self.sale_journal)
        move.action_post()

        move.write({"reason": reason.name})
        move.button_cancel()
        self.assertEqual(move.state, "cancel")
        self.assertTrue(move.inalterable_hash)

        with self.assertRaises(UserError):
            move.write({"date": fields.Date.today() - timedelta(days=1)})
        with self.assertRaises(ValidationError):
            move.write({"partner_id": self.partner_no_ref.id})

    def test_locked_partner_reference_cannot_be_changed(self):
        """A partner locked by a certified posting can't have its reference
        (SAF-T CustomerID) changed afterwards."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()
        self.assertEqual(self.partner.state, "locked")

        with self.assertRaises(ValidationError):
            self.partner.write({"ref": "CHANGED"})

    def test_locked_partner_cannot_be_unlocked_without_force_write(self):
        """Unlocking a locked partner requires the ``force_write`` context —
        the same bypass convention used everywhere else in this module."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()

        with self.assertRaises(ValidationError):
            self.partner.write({"state": "open"})

        self.partner.with_context(force_write=True).write({"state": "open"})
        self.assertEqual(self.partner.state, "open")

    def test_locked_product_reference_cannot_be_changed(self):
        """A product locked by a certified posting can't have its internal
        reference (SAF-T ProductCode) changed afterwards."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()
        self.assertEqual(self.product.state, "locked")

        with self.assertRaises(ValidationError):
            self.product.write({"default_code": "CHANGED"})

    def test_locked_product_cannot_be_unlocked_without_force_write(self):
        """Unlocking a locked product requires the ``force_write`` context."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()

        with self.assertRaises(ValidationError):
            self.product.write({"state": "open"})

        self.product.with_context(force_write=True).write({"state": "open"})
        self.assertEqual(self.product.state, "open")

    def test_locked_product_without_company_reference_cannot_be_changed(self):
        """Regression test: ``product.template``'s ``default_code`` is a
        related field to the (single) variant's — editing it from the
        template form writes through to ``product.product.write()``,
        bypassing ``ProductTemplate.write()``'s own guard. The constrains
        method (``_check_default_code_generation_type``) only blocks this
        for products with a PT/AO ``company_id`` set — most products are
        company-agnostic (``company_id`` empty, as here), so only the direct
        check in ``ProductProduct.write()`` covers this case."""
        product = self.env["product.product"].create(
            {
                "name": "Company-less Certified Product",
                "default_code": "PROD-NOCOMP",
                "type": "service",
                "lst_price": 50.0,
                "taxes_id": [Command.set(self.tax_sale.ids)],
            }
        )
        self.assertFalse(product.company_id)

        move = self._create_invoice(self.sale_journal, product=product)
        move.action_post()
        self.assertEqual(product.state, "locked")

        with self.assertRaises(ValidationError):
            product.write({"default_code": "CHANGED"})

    def test_document_type_code_cannot_be_changed_once_used(self):
        """The document type's ``code`` (sent to the AT as ``tipoDoc``) can't
        be changed once a non-draft document has been emitted with it."""
        doc_type = self.env["account.document.type"].create(
            {
                "name": "Test Invoice Type",
                "code": "ZZ",
                "category": "invoicing",
                "country_id": self.env.ref("base.ao").id,
                "is_refund": False,
            }
        )
        self.sale_journal.document_type_id = doc_type.id

        move = self._create_invoice(self.sale_journal)
        self.assertEqual(move.state, "draft")
        # Not used by any non-draft document yet — still editable.
        doc_type.write({"name": "Renamed While Draft"})

        move.action_post()
        self.assertEqual(move.document_type_id, doc_type)

        with self.assertRaises(ValidationError):
            doc_type.write({"code": "YY"})
        with self.assertRaises(ValidationError):
            doc_type.write({"category": "sales"})

        # Unrelated fields (e.g. name) stay editable.
        doc_type.write({"name": "Renamed After Use"})

        doc_type.with_context(force_write=True).write({"code": "YY"})
        self.assertEqual(doc_type.code, "YY")

    def test_draft_receipt_can_still_be_deleted(self):
        """A receipt that was never posted (no hash) can be deleted
        normally — the restriction only applies once hashed.

        Note: AO customer receipts aren't hashed at all yet (the
        ``pt_arxi_inalterable_hash`` pipeline — ``_pt_arxi_hash_moves`` — is
        PT-only, in ``l10n_pt_certificate``, not installed here); the
        hashed-receipt cannot-be-reset-to-draft/deleted cases are tested in
        ``l10n_pt_certificate`` instead, where that pipeline actually runs."""
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()
        payment_journal = self.env["account.journal"].search(
            [("company_id", "=", self.company.id), ("type", "in", ("bank", "cash"))],
            limit=1,
        )
        payment_journal.l10n_cert = True
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": invoice.partner_id.id,
                "amount": invoice.amount_total,
                "journal_id": payment_journal.id,
                "invoice_ids": [Command.set(invoice.ids)],
                "date": fields.Date.today(),
            }
        )
        self.assertEqual(payment.state, "draft")
        self.assertFalse(payment.move_id.pt_arxi_inalterable_hash)

        payment.unlink()
        self.assertFalse(payment.exists())

    def test_certified_invoice_payment_blocked_on_uncertified_journal(self):
        """A payment reconciling a certified invoice must itself be posted
        on a certified journal, even when created manually (bypassing the
        register-payment wizard, which only filters journal choices in the
        UI — see ``_get_batch_available_journals``/
        ``_compute_available_journal_ids`` in ``wizard/account_register_payment.py``).

        Regression test: this used to be enforced nowhere at the model
        level, so a manually-created ``account.payment`` (or one built via
        API with ``invoice_ids`` set programmatically) could post fine on a
        non-certified journal for a certified invoice.
        """
        invoice = self._create_invoice(self.sale_journal)
        invoice.action_post()
        uncertified_payment_journal = self.env["account.journal"].create(
            {
                "name": "Uncertified Bank",
                "type": "bank",
                "code": "UBNK",
                "company_id": self.company.id,
                "l10n_cert": False,
            }
        )
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": invoice.partner_id.id,
                "amount": invoice.amount_total,
                "journal_id": uncertified_payment_journal.id,
                "invoice_ids": [Command.set(invoice.ids)],
                "date": fields.Date.today(),
            }
        )

        with self.assertRaises(ValidationError):
            payment.action_post()

    def test_non_self_billing_purchase_on_cert_journal_not_processed_as_certified(
        self,
    ):
        """A purchase document posted to a certified (self-billing) purchase
        journal but NOT flagged ``pt_arxi_is_self_billing`` must not go
        through the certified-purchase pipeline (partner/product locking).

        Regression test for an operator-precedence bug in
        ``_pt_arxi_post_finalize``'s filter (``... and (r.is_sale_document()
        and r.journal_id.l10n_cert) or r.is_purchase_document()``): the
        missing parentheses meant *any* ``is_purchase_document()`` on a
        ``l10n_cert`` journal was treated as certified, regardless of the
        self-billing flag — e.g. an ordinary vendor bill mistakenly posted
        to the self-billing journal (a realistic ORM/import-level state,
        since ``pt_arxi_is_self_billing`` only syncs with the journal via UI
        onchange, not on ``create()``) would incorrectly lock the vendor and
        products."""
        self_billing_partner = self.env["res.partner"].create(
            {"name": "Self-billing Vendor", "ref": "SBV001"}
        )
        self_billing_journal = self.env["account.journal"].create(
            {
                "name": "Self-billing Purchases",
                "type": "purchase",
                "code": "SB",
                "company_id": self.company.id,
                "l10n_cert": True,
                "self_billing_partner": self_billing_partner.id,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "journal_id": self_billing_journal.id,
                "partner_id": self_billing_partner.id,
                "pt_arxi_is_self_billing": False,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_no_ref.id,
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            # product_no_ref's default tax is a sale tax
                            # (self.tax_sale) — irrelevant to this test and
                            # incompatible with a purchase fiscal position.
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        move.action_post()

        self.assertEqual(move.state, "posted")
        self.assertNotEqual(self.product_no_ref.state, "locked")

    def test_non_pt_ao_company_does_not_lock_partner_or_product(self):
        """None of these certification rules apply outside PT/AO — a
        certified-looking document (``l10n_cert=True``) in another country
        doesn't lock its partner/product and behaves like standard Odoo,
        since every hook in this module is gated on
        ``country_code in ('PT', 'AO')``."""
        other_company = self.env["res.company"].create(
            {
                "name": "Non-PT/AO Test Company",
                "country_id": self.env.ref("base.us").id,
            }
        )
        self.env.user.write({"company_ids": [Command.link(other_company.id)]})
        self.env["account.chart.template"].try_loading(
            "generic_coa", company=other_company
        )
        other_journal = self.env["account.journal"].create(
            {
                "name": "Certified-looking Sales",
                "type": "sale",
                "code": "FTX",
                "company_id": other_company.id,
                "l10n_cert": True,
                "restrict_mode_hash_table": True,
            }
        )
        partner = self.env["res.partner"].create({"name": "Foreign Customer"})
        product = self.env["product.product"].create(
            {"name": "Foreign Product", "type": "service", "lst_price": 10.0}
        )
        move = (
            self.env["account.move"]
            .with_company(other_company)
            .create(
                {
                    "move_type": "out_invoice",
                    "journal_id": other_journal.id,
                    "partner_id": partner.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": product.id,
                                "quantity": 1.0,
                                "price_unit": 10.0,
                            }
                        )
                    ],
                }
            )
        )
        move.action_post()

        self.assertEqual(move.state, "posted")
        self.assertNotEqual(partner.state, "locked")
        self.assertNotEqual(product.state, "locked")
        # No reference is *required* either, since the SAF-T data-requirement
        # check (_pt_arxi_check_certified_line_requirements) is also gated
        # on country_code in ('PT', 'AO'). Whether the partner actually has
        # one depends on automatic_refs' own Auto/Manual setting, which is
        # global and not country-gated — out of scope for this assertion.
