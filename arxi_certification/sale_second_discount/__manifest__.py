{
    'name': 'Second Sales Discounts',
    'summary': """
        Module that adds discount fields to sale order line
    """,

    'author': "ARXILEAD",
    'website': 'https://www.arxi.pt',
    'category': 'Accounting & Finance',
    'sequence': 151,
    'version': '1.0',
    'license': 'OPL-1',
    'depends': ['l10n_pt_ao_sale', 'display_total_discount'],
    'data': [
        'views/sale_views.xml',
        'report/sale_order_templates.xml',
    ],
}
