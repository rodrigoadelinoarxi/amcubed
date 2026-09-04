{
    'name': 'Subscriptions - Portugal / Angola',
    'summary': """
        Module for common subscription requirements between Portuguese and Angolan localizations""",
    'author': "ARXILEAD",
    'website': "https://www.arxi.pt",
    'category': 'Sales/Subscriptions',
    'version': '1.2',
    'license': 'OPL-1',
    'depends': ['l10n_pt_ao_sale', 'sale_subscription'],
    'external_dependencies' : {
    },
    'data': [
        'data/sale_order_type.xml',
        'views/sale_order_journal_views.xml',
        'views/sale_subscription_views.xml',
        'views/sale_order_views.xml',
        'report/sale_order_templates.xml'
    ],
    'demo': [
    ],
    'auto_install': True,
    'post_init_hook': 'post_init_hook'
}
