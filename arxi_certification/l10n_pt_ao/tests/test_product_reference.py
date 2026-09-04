"""Regression tests for the 2026-08-24 fix (UAT 12): product internal
reference (``default_code``) must not accept characters unsupported by the
SAF-T export charset, must be unique (exact match only — a trailing space
is a different string, not a duplicate), and the product ``type`` must be
immutable once the product is used in a certified document — same as
``default_code``/``name`` already were.

Also pins the fix for a false positive found while validating this: locking
a product and then letting any *unrelated* ORM flush happen (not touching
``default_code`` at all) used to spuriously raise "cannot modify the
internal reference" — the "locked" guard in
``_check_default_code_generation_type``/``_check_default_code_generation_type_template``
now compares against the record's original (``_origin``) value instead of
just checking ``state``.
"""

from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestProductReference(AccountTestCertifiedCommon):

    def test_emoji_blocked(self):
        with self.assertRaises(ValidationError):
            self.env["product.product"].create(
                {
                    "name": "Emoji product",
                    "default_code": "ABC\U0001F600",
                    "type": "service",
                    "company_id": self.company.id,
                }
            )

    def test_accented_char_allowed(self):
        p = self.env["product.product"].create(
            {
                "name": "Acento product",
                "default_code": "ABÇ123",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        self.assertEqual(p.default_code, "ABÇ123")

    def test_duplicate_blocked_same_company(self):
        self.env["product.product"].create(
            {
                "name": "Dup1",
                "default_code": "DUPCODE",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["product.product"].create(
                {
                    "name": "Dup2",
                    "default_code": "DUPCODE",
                    "type": "service",
                    "company_id": self.company.id,
                }
            )

    def test_trailing_space_not_duplicate(self):
        self.env["product.product"].create(
            {
                "name": "Space1",
                "default_code": "SPCODE",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        p2 = self.env["product.product"].create(
            {
                "name": "Space2",
                "default_code": "SPCODE ",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        self.assertEqual(p2.default_code, "SPCODE ")

    def test_global_product_clashes_with_company_specific(self):
        self.env["product.product"].create(
            {"name": "Global1", "default_code": "GLOBALCODE", "type": "service"}
        )
        with self.assertRaises(ValidationError):
            self.env["product.product"].create(
                {
                    "name": "CompanySpecific",
                    "default_code": "GLOBALCODE",
                    "type": "service",
                    "company_id": self.company.id,
                }
            )

    def test_type_locked_with_assertraises(self):
        """Reproduces the side-finding exactly as it happened: lock the
        product, then let assertRaises's own flush/savepoint entry force a
        flush cycle before the actual offending write happens."""
        product = self.env["product.product"].create(
            {
                "name": "Locked type test",
                "default_code": "LOCKEDTYPE",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        product.write({"state": "locked"})
        with self.assertRaises(ValidationError):
            product.product_tmpl_id.write({"type": "consu"})

    def test_lock_then_unrelated_flush_does_not_false_positive(self):
        """The bug found while validating UAT 12: locking a product and
        then merely flushing (without touching default_code) must NOT
        raise "cannot modify the internal reference"."""
        product = self.env["product.product"].create(
            {
                "name": "Lock no-op flush test",
                "default_code": "LOCKNOOP",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        product.write({"state": "locked"})
        # This alone used to raise before the _origin comparison fix.
        self.env.flush_all()
        self.assertEqual(product.default_code, "LOCKNOOP")

    def test_default_code_change_still_blocked_when_locked(self):
        """The actual protection must still work: really changing the
        reference on a locked product is still forbidden."""
        product = self.env["product.product"].create(
            {
                "name": "Real change test",
                "default_code": "REALCHANGE",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        product.write({"state": "locked"})
        with self.assertRaises(ValidationError):
            product.write({"default_code": "REALCHANGE2"})

    def test_shared_product_gets_reference_instead_of_staying_empty(self):
        """UAT 12 (Flávia/Paulo/Matias), root cause found 2026-08-26: a
        company-agnostic product (``company_id`` empty, shared by every
        company) created with neither ``default_code`` nor ``company_id``
        genuinely touched never fires ``@api.constrains`` at all — Odoo
        doesn't trigger a constrain for fields absent from (or equal to
        the default in) ``create()``'s vals. This is exactly how Odoo's own
        attribute/variant generation creates ``product.product`` records
        (subscription plans commonly use attributes for billing
        period/tier) — reported as "subscription products lose their
        reference silently".

        Raising here would be worse than the original bug: it would break
        Odoo's own variant generation, which never sets these fields
        either. Instead, ``_pt_arxi_fill_orphan_variant_reference`` fills a
        real reference after creation whenever one is still missing on a
        company-agnostic product in a PT/AO-relevant database — the
        product never ends up with a silently empty reference — checked
        here in Manual mode, where the pre-existing Automatic-mode
        auto-fill (the ``if`` branch above, unchanged) doesn't apply and
        wouldn't already mask the gap."""
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        product = self.env["product.product"].create(
            {
                "name": "Shared product without reference",
                "type": "service",
                "company_id": False,
            }
        )
        self.assertTrue(product.default_code)

    def test_skip_automatic_ref_context_still_bypasses_the_fill(self):
        """The explicit escape hatch (used by tests that need a genuinely
        empty reference) must still work now that the fill also runs
        outside of Automatic mode."""
        product = (
            self.env["product.product"]
            .with_context(skip_automatic_ref=True)
            .create(
                {
                    "name": "Deliberately empty reference",
                    "type": "service",
                    "company_id": False,
                }
            )
        )
        self.assertFalse(product.default_code)

    def test_shared_product_not_pt_ao_relevant_is_unaffected(self):
        """Sanity check: a product explicitly scoped to a non-PT/AO company
        is never subject to this rule — mirrors the other two constrains'
        behaviour."""
        non_pt_ao = self.env["res.company"].create(
            {"name": "Non PT/AO", "country_id": self.env.ref("base.us").id}
        )
        product = (
            self.env["product.product"]
            .with_context(skip_automatic_ref=True)
            .create(
                {
                    "name": "Non PT/AO product",
                    "type": "service",
                    "company_id": non_pt_ao.id,
                }
            )
        )
        self.assertFalse(product.default_code)

    # -------------------------------------------------------------------
    # product.template create() — UAT vendas/stock, ponto 6 (2026-08-27):
    # a default_code typed on a brand new product.template used to get
    # silently lost before either "already used"/"missing reference"
    # constrain ever saw the value the caller actually asked for. See
    # ProductTemplate.create()'s own docstring for the full mechanism.
    # -------------------------------------------------------------------

    def test_template_duplicate_default_code_blocked_manual_mode(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        self.env["product.product"].create(
            {
                "name": "Original",
                "default_code": "TPLDUP1",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError) as cm:
            self.env["product.template"].create(
                {
                    "name": "Duplicate via template",
                    "default_code": "TPLDUP1",
                    "type": "service",
                    "company_id": self.company.id,
                }
            )
        # Must be the actual duplicate-reference message, not the
        # unrelated "created without an internal reference" one that
        # used to fire against the lost value instead.
        self.assertIn("already used", str(cm.exception))

    def test_template_duplicate_default_code_blocked_automatic_mode(self):
        """Automatic mode used to silently replace the typed duplicate
        with a freshly auto-generated code instead of raising at all."""
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "1"
        )
        self.env["product.product"].create(
            {
                "name": "Original",
                "default_code": "TPLDUP2",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                {
                    "name": "Duplicate via template",
                    "default_code": "TPLDUP2",
                    "type": "service",
                    "company_id": self.company.id,
                }
            )

    def test_template_legitimate_default_code_kept_manual_mode(self):
        """The fix must not regress the normal, non-colliding case — the
        typed value must actually be kept, not silently replaced."""
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        template = self.env["product.template"].create(
            {
                "name": "Legitimate product",
                "default_code": "TPLOK1",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        self.assertEqual(template.default_code, "TPLOK1")

    def test_template_no_default_code_still_required_manual_mode(self):
        """Records with no default_code at all must still go through the
        normal "missing reference" block in Manual mode — only the ones
        that actually had a value take the special create() path."""
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                {
                    "name": "No reference at all",
                    "type": "service",
                    "company_id": self.company.id,
                }
            )

    def test_template_company_agnostic_gets_reference_instead_of_staying_empty(self):
        """UAT POS/contabilidade, ponto 1 (Paulo/Matias, 2026-08-28)
        investigation: a company-agnostic ``product.template`` (no
        explicit ``company_id``, the normal state right after opening the
        "New product" form) must still end up with a real reference —
        just deferred, via ``_pt_arxi_fill_orphan_variant_reference`` on
        the underlying variant, exactly like ``product.product`` already
        does (see ``test_shared_product_gets_reference_instead_of_
        staying_empty`` above). Tried making this constrain raise
        up-front like its sibling and it broke that working deferred-fill
        design instead of closing a real gap — this pins the actual,
        correct behaviour so it doesn't regress again."""
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        template = self.env["product.template"].create(
            {
                "name": "Company-agnostic template, no reference",
                "type": "service",
            }
        )
        self.assertTrue(template.default_code)

    def test_template_mixed_batch_create_default_codes_preserved_in_order(self):
        """A single create() call mixing records with and without an
        explicit default_code must return them in the original order,
        each with the right value."""
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "1"
        )
        templates = self.env["product.template"].create(
            [
                {
                    "name": "First (explicit)",
                    "default_code": "TPLBATCH1",
                    "type": "service",
                    "company_id": self.company.id,
                },
                {
                    "name": "Second (auto)",
                    "type": "service",
                    "company_id": self.company.id,
                },
                {
                    "name": "Third (explicit)",
                    "default_code": "TPLBATCH3",
                    "type": "service",
                    "company_id": self.company.id,
                },
            ]
        )
        self.assertEqual(
            templates.mapped("name"),
            ["First (explicit)", "Second (auto)", "Third (explicit)"],
        )
        self.assertEqual(templates[0].default_code, "TPLBATCH1")
        self.assertTrue(templates[1].default_code)
        self.assertEqual(templates[2].default_code, "TPLBATCH3")

    # -------------------------------------------------------------------
    # product.product create() — second bug found while chasing ponto 6:
    # creating a product.product *directly* (not via product.template)
    # with an explicit default_code, in Manual mode, always failed with
    # "created without an internal reference" even though one was given
    # — confirmed pre-existing on unmodified code, unrelated to the
    # product.template fix above. Existing test_duplicate_blocked_same_
    # company never caught this because it runs in this env's default
    # Automatic mode, which happens to mask it (the "no reference"
    # branch is skipped outright in that mode).
    # -------------------------------------------------------------------

    def test_product_explicit_default_code_kept_manual_mode(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        product = self.env["product.product"].create(
            {
                "name": "Explicit code product",
                "default_code": "PRODEXPL1",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        self.assertEqual(product.default_code, "PRODEXPL1")

    def test_product_no_default_code_still_required_manual_mode(self):
        """Regression guard: the fix above must not accidentally disable
        the "no reference" rule for products with no code at all."""
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        with self.assertRaises(ValidationError):
            self.env["product.product"].create(
                {
                    "name": "No reference at all",
                    "type": "service",
                    "company_id": self.company.id,
                }
            )

    def test_product_duplicate_default_code_blocked_manual_mode(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        self.env["product.product"].create(
            {
                "name": "Original",
                "default_code": "PRODDUP1",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError) as cm:
            self.env["product.product"].create(
                {
                    "name": "Duplicate",
                    "default_code": "PRODDUP1",
                    "type": "service",
                    "company_id": self.company.id,
                }
            )
        self.assertIn("already used", str(cm.exception))

    # -------------------------------------------------------------------
    # UAT vendas/stock, ponto 7 (2026-08-27): "Apagar a referência de um
    # artigo (deixar em branco)". Reproduced live: blanking default_code
    # on an EXISTING product via write() saved fine in Manual mode too
    # (create()'s own constrain doesn't run on write() unless it's
    # re-triggered — it is, via @api.constrains, but confirming here as
    # a regression guard since it's a different code path than create()).
    # Automatic mode intentionally still allows it — the UAT script's own
    # note says so explicitly ("se a empresa estiver configurada com
    # referências automáticas este teste pode não dar erro").
    # -------------------------------------------------------------------

    def test_write_blank_ref_blocked_manual_mode(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        product = self.env["product.product"].create(
            {
                "name": "Has a reference",
                "default_code": "PRODWRITE1",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            product.write({"default_code": False})

    def test_write_blank_ref_blocked_manual_mode_via_template_form(self):
        """Same scenario, but through the template form (the actual UAT
        steps: open a product, clear the field, save) — writes through
        to the variant's default_code via the inverse, exercising a
        different path than a direct product.product.write()."""
        self.env["ir.config_parameter"].sudo().set_param(
            "automatic_refs.product_default_code_type", "0"
        )
        template = self.env["product.template"].create(
            {
                "name": "Has a reference (template)",
                "default_code": "PRODWRITE2",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            f = Form(template)
            f.default_code = ""
            f.save()

    def test_write_blank_ref_allowed_automatic_mode(self):
        """Not a bug: the UAT script itself documents this as expected
        when automatic references are enabled."""
        product = self.env["product.product"].create(
            {
                "name": "Has a reference, automatic mode",
                "default_code": "PRODWRITE3",
                "type": "service",
                "company_id": self.company.id,
            }
        )
        product.write({"default_code": False})
        self.assertFalse(product.default_code)
