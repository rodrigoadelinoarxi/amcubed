# -*- coding: utf-8 -*-
{
    'name'       : "Credit Note No Origin",

    'summary'    : """
       A module to handle credit notes without origin in Odoo.""",
    'description': """
This module allows the creation of credit notes without an origin in Odoo. It is particularly useful for cases where a credit note needs to be issued without a corresponding invoice or sale order, providing flexibility in financial transactions.
   """,

    'author'     : "ARXILEAD",
    'website'    : "https://www.arxi.pt",

    'category'   : 'Uncategorized',
    'version'    : '1.0.1',
    'license': 'OPL-1',

    # any module necessary for this one to work correctly
    'depends'    : ['account', 'l10n_pt_ao'],
    'data'       : [
        'security/ir.model.access.csv',

        'wizards/missing_refund_origin_wizard_view.xml',
    ],
}
