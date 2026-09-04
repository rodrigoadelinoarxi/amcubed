"""Header-field and cancellation guards on certified sale orders.

Pins two 2026-08-21 fixes from the sale/stock v19 UAT triage:

#2 — A certified (hashed) sale order must not let its header fields that
     re-price the immutable lines change: ``pricelist_id``, ``currency_id``
     and ``partner_id`` (the customer is SAF-T-relevant and, like on the
     invoice side — see ``l10n_pt_ao`` ``test_confirmed_document_value_
     fields_blocked`` — must stay frozen once hashed). Drafts stay fully
     editable; writing the same value is a no-op, not a block.

#3-adjacent / #4 — A certified sale order can never be cancelled silently.
     The form path asks for a reason through a wizard, but the list-view
     mass-cancel path calls ``_action_cancel`` directly, bypassing that.
     The guard in ``_action_cancel`` blocks certified orders unless the
     cancellation was authorised (``disable_cancel_warning``/``force_cancel``,
     stamped after a reason was stated). The mass-cancel wizard enforces a
     reason and then authorises; the form reason wizard does the same.

``sale.order.journal.l10n_pt_ao_certified`` only turns True via the
``l10n_pt_cert`` field added by ``l10n_pt_sale`` (a different, optional
repo not among this module's dependencies), so the compute is patched here
to force a certified journal locally — same approach as
``test_negative_lines``. The ``pt_arxi_inalterable_hash`` is stamped
directly on the order: the real signing pipeline lives in a separate
module, and the guards under test only read the field's presence.
"""

from odoo import Command
from odoo.addons.l10n_pt_ao.tests.test_l10n_pt_ao_common import (
    AccountTestCertifiedCommon,
)
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCertifiedSaleOrderGuards(AccountTestCertifiedCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        sequence = cls.env["ir.sequence"].search(
            [("code", "=", "sale.order")], limit=1
        )
        sale_type = cls.env["sale.order.type"].search([], limit=1)
        cls.sale_order_journal = cls.env["sale.order.journal"].create(
            {
                "name": "Certified Sale Orders",
                "sequence_id": sequence.id,
                "sale_type_id": sale_type.id,
                "company_id": cls.company.id,
            }
        )
        cls.other_partner = cls.env["res.partner"].create(
            {
                "name": "Another Certified Customer",
                "ref": "CUST999",
                "country_id": cls.env.ref("base.ao").id,
                "company_id": False,
            }
        )

    def setUp(self):
        super().setUp()

        def _force_certified(recs):
            for rec in recs:
                rec.l10n_pt_ao_certified = True

        self.patch(
            type(self.env["sale.order.journal"]),
            "is_sale_journal_l10n_pt_ao_certified",
            _force_certified,
        )
        self.sale_order_journal.invalidate_recordset(["l10n_pt_ao_certified"])

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _create_order(self, partner=None):
        return self.env["sale.order"].create(
            {
                "partner_id": (partner or self.partner).id,
                "sale_journal": self.sale_order_journal.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": self.product.lst_price,
                        }
                    ),
                ],
            }
        )

    def _certify(self, order):
        """Bring the order to the certified+hashed state the guards key off,
        without the real signing pipeline (a separate module)."""
        order.state = "sale"
        order.pt_arxi_inalterable_hash = "TESTHASH=="
        return order

    # ------------------------------------------------------------------ #
    # #2 — header fields frozen on a certified document
    # ------------------------------------------------------------------ #
    def test_partner_id_blocked_on_certified_order(self):
        """Changing the customer of a certified, hashed order is blocked."""
        order = self._certify(self._create_order())
        with self.assertRaises(UserError):
            order.write({"partner_id": self.other_partner.id})

    def test_partner_id_same_value_not_blocked(self):
        """Writing the current customer back (a no-op) is not a change and
        must not trip the guard."""
        order = self._certify(self._create_order())
        # no exception expected
        order.write({"partner_id": order.partner_id.id})

    def test_partner_id_editable_on_draft(self):
        """A draft on a certified journal (not yet hashed) stays editable —
        the guard only fires once the document carries a hash."""
        order = self._create_order()
        self.assertFalse(order.pt_arxi_inalterable_hash)
        order.write({"partner_id": self.other_partner.id})
        self.assertEqual(order.partner_id, self.other_partner)

    def test_pricelist_id_blocked_on_certified_order(self):
        """Changing the pricelist (which re-prices the hashed lines) is
        blocked on a certified, hashed order."""
        order = self._certify(self._create_order())
        other_pricelist = self.env["product.pricelist"].create(
            {"name": "Other PL", "currency_id": self.company.currency_id.id}
        )
        with self.assertRaises(UserError):
            order.write({"pricelist_id": other_pricelist.id})

    def test_force_change_context_bypasses_guard(self):
        """The guard yields to an explicit ``force_change`` context, the
        documented escape hatch for legitimate system-driven corrections."""
        order = self._certify(self._create_order())
        # no exception expected
        order.with_context(force_change=True).write(
            {"partner_id": self.other_partner.id}
        )
        self.assertEqual(order.partner_id, self.other_partner)

    # ------------------------------------------------------------------ #
    # #4 — cancellation of certified orders
    # ------------------------------------------------------------------ #
    def test_action_cancel_alerts_when_certified_invoice_attached(self):
        """UAT vendas/stock, ponto 11 (2026-08-27): cancelling an order
        that has a non-cancelled certified invoice attached must never go
        through silently — ``action_cancel`` must open the alert wizard
        instead of cancelling straight away, before even reaching the
        reason wizard. Uses a draft invoice (not actually posted/hashed —
        the real signing pipeline lives in a separate module): the guard
        only checks ``state != 'cancel'`` and ``l10n_cert``, both true for
        a draft move on a certified journal."""
        order = self._certify(self._create_order())
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": order.partner_id.id,
                "journal_id": self.sale_journal.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": self.product.lst_price,
                            "sale_line_ids": [Command.link(order.order_line.id)],
                        }
                    )
                ],
            }
        )
        self.assertTrue(invoice.l10n_cert)
        self.assertNotEqual(invoice.state, "cancel")

        result = order.action_cancel()

        self.assertEqual(order.state, "sale", "must not cancel silently")
        self.assertEqual(result.get("res_model"), "sale.order.alert.wizard")

    def test_batch_cancel_certified_blocked_without_authorisation(self):
        """The list-view mass-cancel path (``_action_cancel`` called directly,
        with no authorising context) is blocked for certified orders — the
        silent-cancel bug the UAT reported."""
        order = self._certify(self._create_order())
        with self.assertRaises(UserError):
            order._action_cancel()

    def test_action_cancel_authorised_context_passes(self):
        """The authorised context (what the reason wizard stamps after a
        reason is set) lets ``_action_cancel`` through and stamps the 'A'
        cancellation status."""
        order = self._certify(self._create_order())
        order.reason = "Test reason"
        order.with_context(disable_cancel_warning=True)._action_cancel()
        self.assertEqual(order.state, "cancel")

    def test_mass_cancel_wizard_requires_reason(self):
        """The mass-cancel wizard refuses to run on certified orders when no
        reason is given."""
        order = self._certify(self._create_order())
        wizard = self.env["sale.mass.cancel.orders"].create(
            {"sale_order_ids": [Command.set(order.ids)], "reason": False}
        )
        with self.assertRaises(ValidationError):
            wizard.action_mass_cancel()

    def test_mass_cancel_wizard_with_reason_cancels(self):
        """With a reason, the mass-cancel wizard authorises past the guard,
        cancels the certified orders and records the reason on each."""
        orders = self._certify(self._create_order()) | self._certify(
            self._create_order()
        )
        wizard = self.env["sale.mass.cancel.orders"].create(
            {
                "sale_order_ids": [Command.set(orders.ids)],
                "reason": "Batch cancel reason",
            }
        )
        wizard.action_mass_cancel()
        self.assertTrue(all(o.state == "cancel" for o in orders))
        self.assertTrue(all(o.reason == "Batch cancel reason" for o in orders))

    def test_non_certified_order_batch_cancel_passes(self):
        """A non-certified order is unaffected by the guard and cancels
        straight through the batch path."""
        order = self._create_order()
        order.sale_journal = self.sale_order_journal
        # force the journal to report NOT certified for this one check
        self.patch(
            type(self.env["sale.order.journal"]),
            "is_sale_journal_l10n_pt_ao_certified",
            lambda recs: [setattr(r, "l10n_pt_ao_certified", False) for r in recs],
        )
        order.sale_journal.invalidate_recordset(["l10n_pt_ao_certified"])
        order.state = "sale"
        order._action_cancel()
        self.assertEqual(order.state, "cancel")

    # ------------------------------------------------------------------ #
    # UAT 24 follow-up — new lines blocked on an already-hashed order
    # ------------------------------------------------------------------ #
    def test_new_line_blocked_on_certified_order(self):
        """A new product line can never be added to an already-hashed
        certified order — write()/unlink() already protected editing and
        deleting existing lines; this closes the same gap for creating
        new ones (found investigating UAT 24's upsell report, though that
        exact path turned out unreachable through the real UI — kept as
        defense in depth, see the create() override's own comment)."""
        order = self._certify(self._create_order())
        with self.assertRaises(ValidationError):
            order.order_line.create(
                {
                    "order_id": order.id,
                    "product_id": self.product.id,
                    "product_uom_qty": 1.0,
                    "price_unit": self.product.lst_price,
                }
            )

    def test_new_line_allowed_on_draft(self):
        """A draft order (not yet hashed) stays fully editable — adding a
        line is not blocked."""
        order = self._create_order()
        self.assertFalse(order.pt_arxi_inalterable_hash)
        order.order_line.create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "price_unit": self.product.lst_price,
            }
        )
        self.assertEqual(len(order.order_line), 2)

    def test_downpayment_line_still_allowed_on_certified_order(self):
        """Down-payment lines are exempt (same exemption as unlink()) —
        adding one to an already-hashed order must not be blocked."""
        order = self._certify(self._create_order())
        order.order_line.create(
            {
                "order_id": order.id,
                "is_downpayment": True,
                "product_uom_qty": 1.0,
                "price_unit": 10.0,
            }
        )
        self.assertEqual(len(order.order_line), 2)
