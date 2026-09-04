"""Publishing guards for PT/AO subscription quotations.

1. Plan / recurring-product mismatch was only caught by the core constraint at
   the END of the transaction — after ``action_add_confirmation_info`` had
   already numbered, hashed and committed the order — leaving it
   numbered/hashed/sent despite the error. It is now rejected UP FRONT, before
   the journal switch and the super() call, so a bad order stays a clean draft.

2. The journal ``search`` used to switch to the subscription / normal journal
   did not filter by company, so in a multi-company database it could pick a
   journal from another company and raise a "company inconsistency" on save.
   The three searches now filter by ``self.company_id``.

3. Changing the order's company left the previous company's journal on the
   order (crossover on save). An ``onchange('company_id')`` now re-points the
   journal to one of the new company, keeping the sale type.
"""

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


def _no_confirmation_info(self):
    return True


@tagged("post_install", "-at_install")
class TestSubscriptionPublishGuards(TransactionCase):

    @classmethod
    def _make_pt_company(cls, name):
        company = cls.env["res.company"].create({
            "name": name,
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
        cls.env["account.chart.template"].try_loading("generic_coa", company=company)
        company.account_fiscal_country_id = cls.env.ref("base.pt")
        return company

    @classmethod
    def _make_journals(cls, company):
        normal_type = cls.env.ref("l10n_pt_ao_sale.t_order")
        sub_type = cls.env.ref("l10n_pt_ao_sale_subscription.t_subscription")
        normal = cls.env["sale.order.journal"].create({
            "name": "Quotation %s" % company.id,
            "sale_type_id": normal_type.id,
            "company_id": company.id,
        })
        sub = cls.env["sale.order.journal"].create({
            "name": "Subscription %s" % company.id,
            "sale_type_id": sub_type.id,
            "company_id": company.id,
        })
        return normal, sub

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls._make_pt_company("ARXI Sub Test A")
        cls.company_b = cls._make_pt_company("ARXI Sub Test B")
        cls.env.user.write({
            "company_ids": [Command.link(cls.company_a.id), Command.link(cls.company_b.id)],
            "company_id": cls.company_a.id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company_a.id, cls.company_b.id]
        ))
        cls.company_a = cls.company_a.with_env(cls.env)
        cls.company_b = cls.company_b.with_env(cls.env)

        cls.normal_a, cls.sub_a = cls._make_journals(cls.company_a)
        cls.normal_b, cls.sub_b = cls._make_journals(cls.company_b)

        cls.plan = cls.env["sale.subscription.plan"].create({"name": "Monthly test"})
        cls.partner = cls.env["res.partner"].create({
            "name": "Sub Test Customer",
            "ref": "SUBCUST01",
            "country_id": cls.env.ref("base.pt").id,
        })
        cls.recurring = cls.env["product.product"].create({
            "name": "Recurring", "type": "service", "recurring_invoice": True,
            "default_code": "SUBREC01",
        })
        cls.one_off = cls.env["product.product"].create({
            "name": "One off", "type": "service", "recurring_invoice": False,
            "default_code": "SUBONE01",
        })

    def _order(self, journal, product, plan=None, company=None):
        vals = {
            "partner_id": self.partner.id,
            "sale_journal": journal.id,
            "company_id": (company or self.company_a).id,
            "order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1})],
        }
        if plan:
            vals["plan_id"] = plan.id
        return self.env["sale.order"].create(vals)

    # -- bug 1: mismatch rejected up front, order left untouched -------------
    def test_plan_without_recurring_blocked_before_numbering(self):
        order = self._order(self.sub_a, self.one_off, plan=self.plan)
        self.assertEqual(order.name, "/")
        self.assertEqual(order.state, "draft")
        with self.assertRaises(UserError):
            order.action_quotation_sent()
        # the order must stay a pristine draft: not numbered, not hashed, not sent
        self.assertEqual(order.name, "/")
        self.assertEqual(order.state, "draft")
        self.assertFalse(order.pt_arxi_inalterable_hash)

    # -- legitimate flows still publish -------------------------------------
    def test_valid_subscription_publishes(self):
        order = self._order(self.sub_a, self.recurring, plan=self.plan)
        with patch.object(
            type(order), "action_add_confirmation_info", _no_confirmation_info
        ):
            order.action_quotation_sent()
        self.assertEqual(order.state, "sent")

    def test_plain_quotation_publishes(self):
        order = self._order(self.normal_a, self.one_off)
        with patch.object(
            type(order), "action_add_confirmation_info", _no_confirmation_info
        ):
            order.action_quotation_sent()
        self.assertEqual(order.state, "sent")

    # -- bug 2: journal search is company-scoped on publish -----------------
    def test_publish_keeps_journal_in_document_company(self):
        order = self._order(self.sub_a, self.recurring, plan=self.plan, company=self.company_a)
        with patch.object(
            type(order), "action_add_confirmation_info", _no_confirmation_info
        ):
            order.action_quotation_sent()
        self.assertEqual(order.sale_journal.company_id, self.company_a)

    # -- bug 3: changing company re-points the journal (onchange) -----------
    def test_onchange_company_repoints_journal(self):
        form = Form(self.env["sale.order"].with_context(
            allowed_company_ids=[self.company_a.id, self.company_b.id]
        ))
        form.company_id = self.company_a
        form.partner_id = self.partner
        with form.order_line.new() as line:
            line.product_id = self.one_off
            line.product_uom_qty = 1
        self.assertEqual(form.sale_journal.company_id, self.company_a)

        form.company_id = self.company_b
        self.assertEqual(
            form.sale_journal.company_id, self.company_b,
            "changing company must re-point the sale journal to the new company",
        )
        order = form.save()  # must not raise a company crossover
        self.assertEqual(order.sale_journal.company_id, self.company_b)
