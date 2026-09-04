import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        if 'journal_id' in res:
            res.pop('journal_id')
            journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
            if journal:
                res['journal_id'] = journal.id
        return res
