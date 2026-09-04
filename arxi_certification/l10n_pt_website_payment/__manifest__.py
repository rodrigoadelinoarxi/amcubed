{
    'name': "l10n_pt Website Payment",

    'summary': """
        l10n_pt Website Payment.""",
    'author': "ARXILEAD",
    'website': "https://www.arxi.pt",
    'category': 'Website',
    'version': '1.1',
    'license': 'OPL-1',
    'depends': [
        'l10n_pt_certificate',
        'website_payment'
    ],
    'auto_install': [
        'l10n_pt_certificate',
        'website_payment'
    ],
    'data': [
        'views/account_journal_views.xml',
        'views/account_payment_views.xml'
    ],
    'auto_install': True,
}
