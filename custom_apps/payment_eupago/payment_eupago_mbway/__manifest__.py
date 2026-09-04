{
    'name'       : 'euPago MBWay Payment Acquirer',
    'summary'    : 'Payment Acquirer: euPago MBWay Implementation',
    'author'     : 'Arxi',
    'website'    : 'http://www.arxi.pt',
    'category'   : 'Payment Acquirer',
    'version'    : '17.0.0.0.16',
    'license'    : 'OPL-1',
    # 'price'      : 550.00,
    # 'currency'   : 'EUR',
    'depends'    : [
        'payment_eupago_arxi'
    ],
    'data'       : [
        'views/payment_views.xml',
        'views/payment_eupago_templates.xml',
        'data/payment_method_data.xml',
        'data/payment_acquirer_data.xml',

    ],

    'assets'     : {
        'web.assets_frontend': [
            'payment_eupago_mbway/static/src/js/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
}
