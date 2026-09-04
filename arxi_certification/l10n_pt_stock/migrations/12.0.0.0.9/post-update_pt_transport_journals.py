import odoo
import logging
from odoo import api, _, SUPERUSER_ID
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

MOV_TYPES = {'delivery.document'  : 'Guia de Remessa',
             'returns.document'   : 'Guia de Devolução',
             'own_assets.document': 'Guia de Movimentação de Ativos Fixos Próprios',
             'transport.document' : 'Guia de Transporte'}


def migrate(cr, version):
    registry = odoo.registry(cr.dbname)

    env = api.Environment(cr, SUPERUSER_ID, {})

    # Creates default pt transport journals for each portuguese company
    for company in env['res.company'].search([('partner_id.country_id.code', '=', 'PT')]):
        for mov_type, mov_descr in MOV_TYPES.items():
            if not env['pt.transport.journal'].search_count(
                    [('company_id', '=', company.id), ('movement_type', '=', mov_type)]):
                try:
                    env['pt.transport.journal'].create({
                        'company_id'   : company.id,
                        'name'         : mov_descr,
                        'movement_type': mov_type,
                        'sequence'     : 10,
                    })
                except ValidationError:
                    _logger.info("Unable to create sequence for %s" % mov_descr)
