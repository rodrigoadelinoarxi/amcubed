{
    'name': 'Portugal - Certified Discount Reports',
    'summary': """
        Module for total discount in sale and move reports""",

    'author': "ARXILEAD",
    'website': "https://www.arxi.pt",
    'category': 'Accounting & Finance',
    'version': '1.0',
    'license': 'OPL-1',
    'depends': ['l10n_pt_certificate', 'l10n_pt_sale', 'display_total_discount'],
    'data': [
        'report/account_move_report.xml',
    ],
    'auto_install': True,
}
