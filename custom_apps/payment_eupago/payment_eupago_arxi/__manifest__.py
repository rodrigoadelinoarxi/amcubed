{
    'name': 'euPago Payment Acquirer - Base',

    'summary': 'Payment Acquirer: euPago Implementation',

    'author': 'Arxi',
    'website': 'http://www.arxi.pt',

    'category': 'Payment Acquirer',
    'version': '19.0.0.0.7',
    'license': 'OPL-1',

    # 'price': 550.00,
    # 'currency': 'EUR',

    'depends': ['payment', 'sale'],

    'data': [
        'data/transaction_deadline_cron.xml',
        'views/payment_transaction_views.xml'
    ],

    'images': [
        'static/description/banner.gif',
    ],

    'installable': True,
    'application': True,
}
