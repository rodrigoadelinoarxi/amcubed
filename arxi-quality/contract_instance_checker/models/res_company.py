# -*- coding: utf-8 -*-

from odoo import models, fields


class ResCompany(models.Model):
    """
    Extension of res.company to add contract instance checker fields.
    """
    _inherit = 'res.company'

    contract_nif = fields.Char(
        string='Contract NIF',
        help='Company NIF for contract validation with the central server'
    )

    contract_token = fields.Char(
        string='Contract Token',
        help='Access token provided by the central server'
    )

    contract_central_server_url = fields.Char(
        string='Central Server URL',
        help='Central server URL for contract validation (e.g. https://contract.arxi.pt)',
        default='https://contract.arxi.pt'
    )

    contract_type = fields.Char(
        string='Contract Type',
        help='Contract type code from central server (e.g. flybyodoo, certification, payroll). '
             'Updated automatically during contract validation.',
    )
