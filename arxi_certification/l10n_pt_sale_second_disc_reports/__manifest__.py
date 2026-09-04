{
    'name': 'Portugal - Certified Second Discount Reports',
    'summary': """Module for second discount in sale and move reports""",
    'author': "ARXILEAD",
    'website': "https://www.arxi.pt",
    'category': 'Accounting & Finance',
    'version': '1.1',
    'license': 'OPL-1',
    'depends': ['l10n_pt_total_discount_reports', 'account_second_discount', 'sale_second_discount'],
    'data': [
        'report/sale_order_templates.xml',
        'report/account_move_report.xml',
    ],
    'auto_install': True,
}
