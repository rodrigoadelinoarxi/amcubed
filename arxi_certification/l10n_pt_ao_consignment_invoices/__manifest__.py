# -*- coding: utf-8 -*-
{
    'name': "Consignment Invoices",
    'license': 'OPL-1',
    'summary': """Consignment Invoice Menu""",
    'description': """
        Added Menu Item and Action to view and create Consignment Invoices.
    """,

    'author': "ARXILEAD",
    'website': "https://www.arxi.pt",

    'category': 'Uncategorized',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['l10n_pt_ao_sale'],

    # always loaded
    'data': [
        'views/sale_order_menu.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'post_init_hook'       : 'post_init_hook'
}
