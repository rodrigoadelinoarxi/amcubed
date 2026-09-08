# -*- coding: utf-8 -*-

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _should_block_cert_action(self):
        module = (
            self.env["ir.module.module"]
            .sudo()
            .search(
                [("name", "=", "l10n_pt_sale"), ("state", "=", "installed")], limit=1
            )
        )
        if module:
            if (
                hasattr(self, "sale_journal")
                and self.sale_journal
                and self.sale_journal.l10n_pt_cert
            ):
                return True
            return False
        return True

    def action_confirm(self):
        if self._should_block_cert_action():
            self.env["contract.instance.status"]._check_certification_contract(self)
        return super().action_confirm()

    def action_quotation_sent(self):
        if self._should_block_cert_action():
            self.env["contract.instance.status"]._check_certification_contract(self)
        return super().action_quotation_sent()
