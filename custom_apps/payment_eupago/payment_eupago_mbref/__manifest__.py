{
    'name'          : 'euPago MbRef Payment Acquirer',
    'summary'       : 'Payment Acquirer: euPago MbRef Implementation',
    'author'        : 'Arxi',
    'website'       : 'http://www.arxi.pt',
    'category'      : 'Payment Acquirer',
    'version'       : '17.0.0.0.17',
    'license'       : 'OPL-1',
    # 'price'      : 450.00,
    # 'currency'   : 'EUR',
    'depends'       : [
        'payment_eupago_arxi', 'website'
    ],
    'data'          : [
        'views/payment_views.xml',
        'views/payment_eupago_templates.xml',
        'views/account_move_views.xml',
        'data/payment_method_data.xml',
        'data/payment_acquirer_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable'   : True,
}
