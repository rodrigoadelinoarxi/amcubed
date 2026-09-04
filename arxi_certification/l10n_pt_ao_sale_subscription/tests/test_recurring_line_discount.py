"""Manual discount on recurring subscription lines survives a recompute.

Pins the 2026-08-24 UAT fix (finding E2-L71): a recurring product with a
first/second discount (from sale_second_discount) lost its discount whenever
``_compute_discount`` re-ran (e.g. on plan selection) — the line's ``discount``
went to 0 and the price came out un-discounted, while the 1st/2nd discount
fields still showed values. The cause was ``_should_preserve_manual_discount``
excluding every recurring line (``not self.recurring_invoice``).

The fix narrows the exclusion to upsell lines only
(``subscription_state != '7_upsell'``): upsell must keep yielding to the core's
prorata-temporis discount, but ordinary recurring lines must keep their manual
discount.
"""

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRecurringLineDiscount(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({
            "name": "ARXI Disc Test",
            "country_id": cls.env.ref("base.pt").id,
            "currency_id": cls.env.ref("base.EUR").id,
            "vat": "PT123456789",
            "entity_type": "S",
            "commercial_registry": "LISBOA",
            "company_registry": "123456789",
            "street": "Rua Teste, 1",
            "city": "Lisboa",
            "zip": "1000-001",
            "l10n_pt_at_test": True,
            "tax_calculation_rounding_method": "round_globally",
        })
        cls.env.user.write({
            "company_ids": [Command.link(cls.company.id)],
            "company_id": cls.company.id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids
        ))
        cls.company = cls.company.with_env(cls.env)
        cls.env["account.chart.template"].try_loading("generic_coa", company=cls.company)
        cls.company.account_fiscal_country_id = cls.env.ref("base.pt")

        normal_type = cls.env.ref("l10n_pt_ao_sale.t_order")
        cls.journal = cls.env["sale.order.journal"].create({
            "name": "Quotation disc",
            "sale_type_id": normal_type.id,
            "company_id": cls.company.id,
        })
        cls.plan = cls.env["sale.subscription.plan"].create({"name": "Monthly disc"})
        cls.partner = cls.env["res.partner"].create({
            "name": "Disc Customer", "ref": "DISC01",
            "country_id": cls.env.ref("base.pt").id,
        })
        cls.recurring = cls.env["product.product"].create({
            "name": "Recurring disc", "type": "consu",
            "recurring_invoice": True, "list_price": 100.0, "default_code": "DREC",
        })
        cls.one_off = cls.env["product.product"].create({
            "name": "One off disc", "type": "consu",
            "recurring_invoice": False, "list_price": 150.0, "default_code": "DONE",
        })

    def _order_with_plan(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "sale_journal": self.journal.id,
            "plan_id": self.plan.id,
            "order_line": [
                Command.create({
                    "product_id": self.recurring.id, "product_uom_qty": 1,
                    "price_unit": 100.0, "first_discount": 10.0, "second_discount": 50.0,
                }),
                Command.create({
                    "product_id": self.one_off.id, "product_uom_qty": 3,
                    "price_unit": 150.0, "first_discount": 25.0, "second_discount": 0.0,
                }),
            ],
        })

    def test_recurring_line_keeps_double_discount_with_plan(self):
        """A recurring line with 1st/2nd discount keeps its discount and
        discounted subtotal once a plan is set (E2-L71)."""
        order = self._order_with_plan()
        rec_line = order.order_line.filtered(lambda l: l.recurring_invoice)
        # 100 * (1-0.10) * (1-0.50) = 45
        self.assertAlmostEqual(rec_line.price_subtotal, 45.0, places=2)
        self.assertGreater(rec_line.discount, 0.0)

    def test_non_recurring_line_keeps_discount(self):
        """The non-recurring line is unaffected (regression guard)."""
        order = self._order_with_plan()
        non_line = order.order_line.filtered(lambda l: not l.recurring_invoice)
        # 150 * 3 * (1-0.25) = 337.5
        self.assertAlmostEqual(non_line.price_subtotal, 337.5, places=2)

    def test_ordinary_recurring_line_is_preserved(self):
        """An ordinary recurring line (not upsell) preserves its manual
        discount — the positive side of the guard."""
        order = self._order_with_plan()
        rec_line = order.order_line.filtered(lambda l: l.recurring_invoice)
        self.assertNotEqual(order.subscription_state, "7_upsell")
        self.assertTrue(rec_line._should_preserve_manual_discount())

    def test_upsell_line_yields_to_core_prorata(self):
        """An upsell line must NOT preserve a manual discount — the core sets
        the prorata-temporis discount there, so the guard must return False for
        7_upsell.

        A real upsell needs an invoiced parent subscription (validated
        manually in the UI); here we only prove the guard keys off
        ``subscription_state`` by forcing that value through the env cache
        (writing it would trip the core's upsell multi-currency constraint on a
        non-upsell order)."""
        order = self._order_with_plan()
        rec_line = order.order_line.filtered(lambda l: l.recurring_invoice)
        self.env.cache.set(
            order, order._fields["subscription_state"], "7_upsell"
        )
        self.assertFalse(
            rec_line._should_preserve_manual_discount(),
            "upsell lines must yield to the core prorata discount",
        )

    def test_discount_depends_on_plan_and_start_date(self):
        """Pins the 2026-08-28 UAT 24 fix (Matias: "não é aplicado o
        desconto correto do pro-rata" on a mid-month start date, and
        "o upsell não aplica o desconto pro-rata"): overriding
        ``_compute_discount`` with ``@api.depends('product_id',
        'product_uom_id', 'product_uom_qty')`` — copied from ``sale``'s
        own base depends — silently REPLACED sale_subscription's
        decorator instead of extending it, dropping its
        ``order_id.plan_id``/``order_id.start_date`` triggers ("recompute
        price & discount on plan change" / "recompute prorata temporis
        discount (upsell orders)", the native's own comments). Without
        them, changing the plan or the start date on an already-created
        line never recomputed its discount.

        Odoo keys the whole compute graph off the most-derived class's
        @api.depends for a given method, so this can only be checked at
        the registry's trigger-graph level (recomputing a genuinely
        wrong VALUE would need a full upsell/invoicing setup just to
        prove the trigger even fires) — asserting the graph itself is
        both simpler and the actual mechanism the bug was in.
        """
        triggers = self.env.registry._field_triggers.get(
            self.env["sale.order"]._fields["start_date"], {}
        )
        # Trigger-graph values are Field objects, not plain strings —
        # compare on (model_name, name) instead of assuming a string.
        recomputed = {
            (f.model_name, f.name) for fields in triggers.values() for f in fields
        }
        self.assertIn(
            ("sale.order.line", "discount"), recomputed,
            "order_id.start_date must still trigger sale.order.line.discount "
            "to recompute (dropped by l10n_pt_ao_sale_subscription's "
            "_compute_discount override losing sale_subscription's own "
            "@api.depends)",
        )

    def test_upsell_order_not_flagged_as_subscription(self):
        """Pins the 2026-08-28 UAT 24 fix (Paulo: "O orçamento que deu
        origem ao upsell foi incrementado com uma linha nova e alterou os
        valores"): ``_compute_is_subscription`` classified any PT/AO order
        with a plan_id and only recurring lines as a subscription — an
        upsell order matches that shape (it inherits the parent's
        plan_id and carries recurring lines) but must NOT be one, exactly
        like the base ``sale_subscription`` model itself excludes
        '7_upsell'. Left misclassified, confirming the upsell would turn
        it into a second, standalone subscription duplicating the
        parent's MRR instead of just merging into it. Forced through the
        env cache (like ``test_upsell_line_yields_to_core_prorata`` above)
        since a real upsell needs an invoiced parent subscription."""
        order = self._order_with_plan()
        self.env.cache.set(
            order, order._fields["subscription_state"], "7_upsell"
        )
        order.invalidate_recordset(["is_subscription"])
        self.assertFalse(
            order.is_subscription,
            "an upsell order ('7_upsell') must never compute is_subscription=True",
        )
