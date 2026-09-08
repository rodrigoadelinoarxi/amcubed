# -*- coding: utf-8 -*-

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        self.env["contract.instance.status"]._check_certification_contract(self)
        return super()._post(soft=soft)

    def action_register_payment(self):
        self.env["contract.instance.status"]._check_certification_contract(self)
        return super().action_register_payment()
