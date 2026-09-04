{
    'name': 'Portugal - Certified Sales',
    'summary': """
        Module for sales certification and exporting SAF-T""",

    'author': "ARXILEAD",
    'website': "https://www.arxi.pt",
    'category': 'Accounting & Finance',
    'sequence': 151,
    'version': '1.18',
    'license': 'OPL-1',
    'depends': ['l10n_pt_certificate', 'l10n_pt_ao_sale', 'event_sale'],
    'data': [
        'report/sale_order_templates.xml',
        'data/protected_reports_data.xml',
        'views/sale_order_journal_views.xml',
        'views/sale_order_views.xml'
    ],
    'demo': [
        'demo/account_series.xml',
    ],
    'auto_install': True,
    'post_init_hook': 'post_init_hook'
}
