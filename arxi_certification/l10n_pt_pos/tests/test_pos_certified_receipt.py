"""Unit tests for the certified POS receipt layer added by l10n_pt_pos.

l10n_pt_pos does not compute hashes, series or ATCUD itself: those are produced
on the account.move the pos.order originates, by l10n_pt_certificate/l10n_pt_ao.
This module is the *presentation* layer on the POS receipt — it exposes, off the
pos.order, the QR Code image, the ATCUD and the receipt QR sizing so the OWL
receipt (OrderReceipt.xml) can print them.

These tests therefore verify exactly that layer, without driving the POS UI:

* the pos.order carries the qr_code (compute) and pt_arxi_atcud (related) fields;
* qr_code is empty unless the order is linked to a certified (l10n_cert) move,
  and is a real SVG data-uri built from account_move.data_for_qr_code() when it
  is — i.e. the QR mirrors the certified document, never invents data;
* pt_arxi_atcud mirrors the certified move's ATCUD;
* pos.config.qr_style is composed from the l10n_pt_pos QR size parameters.

They reuse AccountTestPTInvoicingCommon (PT company, database.is_neutralized +
l10n_pt_at_test, certified sale journal), so a certified move can be posted and
hashed locally without the AT webservice or the Arxi central server.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_pt_certificate.tests.test_l10n_pt_common import (
    AccountTestPTInvoicingCommon,
)


@tagged("post_install", "-at_install")
class TestPosCertifiedReceipt(AccountTestPTInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cash_journal = cls.env["account.journal"].create(
            {
                "name": "POS Cash Test",
                "type": "cash",
                "code": "PCSH",
                "company_id": cls.company.id,
            }
        )
        cash_pm = cls.env["pos.payment.method"].create(
            {
                "name": "Cash Test",
                "journal_id": cash_journal.id,
                "company_id": cls.company.id,
            }
        )
        cls.pos_config = cls.env["pos.config"].create(
            {
                "name": "PT Cert POS Test",
                "company_id": cls.company.id,
                "payment_method_ids": [Command.set(cash_pm.ids)],
            }
        )
        cls.pos_config.with_user(cls.env.user).open_ui()
        cls.pos_session = cls.pos_config.current_session_id

    def _make_pos_order(self, account_move=None):
        """A minimal pos.order for the presentation-layer computes. Not a full
        POS flow: we only need the order-to-move link the receipt reads from,
        plus the session the model requires."""
        vals = {
            "company_id": self.company.id,
            "session_id": self.pos_session.id,
            "partner_id": self.partner.id,
            "amount_tax": 0.0,
            "amount_total": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "lines": [],
        }
        if account_move is not None:
            vals["account_move"] = account_move.id
        return self.env["pos.order"].create(vals)

    def test_fields_exist_on_pos_order(self):
        """The receipt layer's fields are declared on pos.order."""
        fields = self.env["pos.order"]._fields
        self.assertIn("qr_code", fields)
        self.assertIn("pt_arxi_atcud", fields)

    def test_qr_code_empty_without_certified_move(self):
        """No certified move -> no QR on the POS receipt (correct: only
        certified documents carry a fiscal QR)."""
        order = self._make_pos_order()
        self.assertFalse(
            order.qr_code, "qr_code must be empty when there is no account_move"
        )

    def test_qr_code_empty_for_uncertified_move(self):
        """A move on a non-l10n_cert journal must not produce a QR: the guard is
        account_move.l10n_cert, not merely the presence of a move."""
        move = self._create_invoice(self.uncertified_sale_journal)
        move.action_post()
        self.assertFalse(move.l10n_cert)
        order = self._make_pos_order(account_move=move)
        self.assertFalse(
            order.qr_code, "uncertified documents must not get a POS QR code"
        )

    def test_qr_code_and_atcud_from_certified_move(self):
        """A certified, posted move -> the POS order exposes an SVG QR built
        from the move's data_for_qr_code(), and the move's ATCUD."""
        move = self._create_invoice(self.sale_journal)
        move.action_post()
        self.assertTrue(move.l10n_cert)
        self.assertTrue(
            move.data_for_qr_code(),
            "sanity: the certified move must have QR data once posted",
        )

        order = self._make_pos_order(account_move=move)

        self.assertTrue(order.qr_code, "certified order must expose a QR image")
        self.assertTrue(
            order.qr_code.startswith("data:image/svg+xml;base64,"),
            "the POS QR must be an SVG data-uri (as printed by OrderReceipt.xml)",
        )
        self.assertEqual(
            order.pt_arxi_atcud,
            move.pt_arxi_atcud,
            "the receipt ATCUD must mirror the certified move's ATCUD",
        )
        self.assertTrue(order.pt_arxi_atcud, "a posted certified move has an ATCUD")

    def test_qr_style_composed_from_parameters(self):
        """pos.config.qr_style is built from the l10n_pt_pos QR size params
        (min/default/uom) — the size the OrderReceipt applies to the QR image."""
        default_size = self.env.ref("l10n_pt_pos.default_pos_qr_size").sudo().value
        uom = self.env.ref("l10n_pt_pos.uom_pos_qr_size").sudo().value
        self.assertEqual(
            self.pos_config.qr_style,
            f"width: {default_size}{uom}; height: {default_size}{uom};",
        )
