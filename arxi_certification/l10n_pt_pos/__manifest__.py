{
    'name'          : 'Portugal - Certified Point of Sale',
    'summary'       : """
        QR Code and ATCUD on the certified POS receipt""",

    'author': "ARXILEAD",
    'website': "https://www.arxi.pt",
    'category': 'Sales/Point Of Sale',
    'version': '1.2',
    'license': 'OPL-1',
    'depends': ['l10n_pt_certificate', 'l10n_pt_ao_pos'],
    'external_dependencies': {
        'python': ['qrcode'],
    },
    'data': [
        'data/pos_qr_parameters.xml',
    ],
    'assets'        : {
        'point_of_sale._assets_pos': [
            'l10n_pt_pos/static/src/js/**/*',
            'l10n_pt_pos/static/src/xml/**/*',
        ],
    },
    'auto_install' : ['l10n_pt_certificate', 'l10n_pt_ao_pos'],
    'application'   : False,
}
