from odoo import SUPERUSER_ID, api
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    journals = env['account.journal'].search([('type', '=', 'sale'), ('l10n_pt_cert', '=', True)])
    for journal in journals:
        invs = env['account.move'].search([('pt_arxi_validated_date', '!=', False),
                                           ('journal_id', '=', journal.id)], order='pt_arxi_validated_date asc')
        vals = {'restrict_mode_hash_table': True}
        journal.write(vals)
        for inv in invs:
            inv.secure_sequence_number = journal.secure_sequence_id.next_by_id()
        invs.flush()
