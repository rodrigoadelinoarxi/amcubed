{
    'name'       : 'euPago MbRef Payment Acquirer Sale',
    'summary'    : 'Payment Acquirer: euPago MbRef Implementation Sale',
    'author'     : 'Arxi',
    'website'    : 'http://www.arxi.pt',
    'category'   : 'Payment Acquirer',
    'version'    : '17.0.0.0.3',
    'license'    : 'OPL-1',
    # 'price'      : 550.00,
    # 'currency'   : 'EUR',
    'depends'    : [
        'payment_eupago_mbref', 'sale'
    ],
    'data'       : [
        'views/sale_order_views.xml',
        'reports/sale_order_mbref_report.xml',
    ],
    'installable': True,
}
