"""Regression tests for UAT 13c/24/24b — the "Faturas de Autofaturação"
action (``account_move_action_self_billing``) not actually landing on a
usable self-billing journal, in two separate ways found on two different
dates:

1. (2026-08-20) The action must default
   ``account.move.pt_arxi_is_self_billing`` to True — not
   ``account.journal.is_self_billing``, a different field on a different
   model that doesn't even exist on ``account.move``, so the old context
   key (``default_is_self_billing``) was a silent no-op. Without
   ``pt_arxi_is_self_billing`` set, ``_compute_suitable_journal_ids`` did
   the opposite of what's needed: it *excluded* journals with a
   ``self_billing_partner`` instead of restricting to them, making the
   dedicated self-billing journal impossible to *select* from this action.

2. (2026-08-25) Even after (1) was fixed, the *default* journal shown
   when the form opens still wasn't the self-billing one:
   ``_search_default_journal`` — a separate method that fills
   ``journal_id`` when the record is created with none — was still
   gated on the exact same stale ``default_is_self_billing`` context key
   the action never sets, so it silently fell through to the native
   "first certified purchase journal" default (an ordinary vendor-bills
   journal), landing on a journal with no self-billing document type
   available at all — reported as "não dá também pelo menu" once (1)
   alone turned out not to be the whole story.
"""

import ast

from odoo.tests import tagged

from .test_l10n_pt_ao_common import AccountTestCertifiedCommon


@tagged("post_install", "-at_install")
class TestSelfBillingJournalSelection(AccountTestCertifiedCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.self_billing_partner = cls.env["res.partner"].create(
            {
                "name": "Self-Billing Supplier",
                "vat": "AO999999999",
                "street": "Rua Teste, 2",
                "city": "Luanda",
                "country_id": cls.env.ref("base.ao").id,
                "allows_self_billing": True,
            }
        )
        cls.self_billing_journal = cls.env["account.journal"].create(
            {
                "name": "Self-Billing Purchases",
                "type": "purchase",
                "code": "AFT",
                "company_id": cls.company.id,
                "l10n_cert": True,
                "source_billing": "P",
                "self_billing_partner": cls.self_billing_partner.id,
            }
        )

    def test_action_context_flags_self_billing_and_journal_selectable(self):
        """Opening the dedicated action must set pt_arxi_is_self_billing on
        the new move, which in turn makes the self-billing journal
        selectable."""
        action = self.env.ref("l10n_pt_ao.account_move_action_self_billing")
        ctx = ast.literal_eval(action.context)

        move = self.env["account.move"].with_context(**ctx).new({})

        self.assertTrue(move.pt_arxi_is_self_billing)
        # suitable_journal_ids on an unsaved (.new()) move holds NewId-wrapped
        # records — compare against the real ones via ._origin.
        self.assertIn(self.self_billing_journal, move.suitable_journal_ids._origin)

    def test_action_context_defaults_journal_to_self_billing_one(self):
        """The dedicated action must not just make the self-billing
        journal *selectable* — it must default to it, instead of an
        ordinary certified purchase journal that happens to sort first.

        Pin the 2026-08-25 mirror of the same bug: ``_search_default_journal``
        (which fills journal_id when the form opens with none) still gated
        on the pre-2026-08-20 context key (``default_is_self_billing``,
        never set by this action), so it fell through to the native
        "first purchase journal" default even from the correct menu."""
        ordinary_journal = self.env["account.journal"].create(
            {
                "name": "Vendor Bills",
                "type": "purchase",
                "code": "VBILL",
                "company_id": self.company.id,
                "l10n_cert": True,
                "source_billing": "P",
            }
        )
        action = self.env.ref("l10n_pt_ao.account_move_action_self_billing")
        ctx = ast.literal_eval(action.context)

        move = self.env["account.move"].with_context(**ctx).new({})

        self.assertEqual(move.journal_id._origin, self.self_billing_journal)
        self.assertNotEqual(move.journal_id._origin, ordinary_journal)

    def test_wrong_context_key_would_hide_the_journal(self):
        """Pin the actual bug: the old (wrong) context key
        ``default_is_self_billing`` doesn't touch ``account.move`` at all,
        so the self-billing journal stays excluded from the suggested
        list."""
        move = (
            self.env["account.move"]
            .with_context(default_is_self_billing=True, default_move_type="in_invoice")
            .new({})
        )

        self.assertFalse(move.pt_arxi_is_self_billing)
        self.assertNotIn(self.self_billing_journal, move.suitable_journal_ids._origin)
