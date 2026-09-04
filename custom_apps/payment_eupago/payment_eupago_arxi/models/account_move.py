from odoo import api, Command, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_violated_lock_dates(self, invoice_date, has_tax):
        if not self.company_id:
            self.company_id = self.journal_id.company_id.id
        res = super(AccountMove,self)._get_violated_lock_dates(invoice_date, has_tax)
        return res