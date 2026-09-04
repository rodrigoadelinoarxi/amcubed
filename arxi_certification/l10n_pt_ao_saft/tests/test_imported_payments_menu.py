"""Regression test for the "Imported Payments" menu added on 2026-08-24
(UAT 42c side-finding): payments created via the SAF-T import wizard are
linked to a self-paid (FR/FS) invoice, so ``is_selfpaid=True`` excludes
them from the main Payments list — same as a normal auto-generated
self-paid receipt (``account.action_account_payments``'s
``is_selfpaid != True`` domain, from ``l10n_pt_ao``). ``is_saft_import``
is the only way to tell the two apart; a dedicated menu
(``saft_imported_payments_action``), filtered on that flag, is where
imported payments can actually be found.
"""
from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install")
class TestImportedPaymentsMenu(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("database.is_neutralized", "1")
        cls.company = next(
            c for c in cls.env["res.company"].search([]) if c.country_code in ("PT", "AO")
        )
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        cls.company = cls.company.with_env(cls.env)
        cls.journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "in", ("bank", "cash"))],
            limit=1,
        )
        cls.partner = cls.env["res.partner"].search(
            [("company_id", "in", (False, cls.company.id))], limit=1
        )

    def _create_payment(self, **extra_vals):
        vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": 10.0,
            "journal_id": self.journal.id,
            "date": fields.Date.today(),
            "is_selfpaid": True,
        }
        vals.update(extra_vals)
        return self.env["account.payment"].create(vals)

    def test_imported_payment_found_only_in_dedicated_menu(self):
        imported = self._create_payment(is_saft_import=True)
        normal_selfpaid = self._create_payment()

        action = self.env.ref("l10n_pt_ao_saft.saft_imported_payments_action")
        found = self.env["account.payment"].search(safe_eval(action.domain))
        self.assertIn(imported.id, found.ids)
        self.assertNotIn(normal_selfpaid.id, found.ids)

    def test_both_kinds_excluded_from_main_payments_menu(self):
        imported = self._create_payment(is_saft_import=True)
        normal_selfpaid = self._create_payment()

        main_action = self.env.ref("account.action_account_payments")
        found = self.env["account.payment"].search(
            safe_eval(main_action.domain) + [("id", "in", (imported.id, normal_selfpaid.id))]
        )
        self.assertFalse(found)
