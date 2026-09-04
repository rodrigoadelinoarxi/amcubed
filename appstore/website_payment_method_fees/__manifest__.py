# -*- coding: utf-8 -*-

{
    'name': 'Payment Method Fees for Website Sales',
    'version': '17.1',
    'category': 'eCommerce',
    'summary': 'eCommerce Payment Fees Manager, Website Payment Fees, Checkout Extra Fees, Payment Method Fee Calculation, Website Transaction Fee, Payment Method Surcharge, Website Sale Extra Fees, Odoo Payment Fees Integration, Dynamic Payment Fees, Custom Payment Method Surcharge, eCommerce Checkout Fee Manager, Payment Gateway Fees, Online Payment Fee Processor, Sale Order Payment Fees, Transaction Fee Manager, Website Sale Payment Surcharge, Custom Checkout Fee Handler, eCommerce Fee Calculator, Payment Method Charge Manager, Checkout Fee Integration website service charge fees charge service fees payment service charge payment fees payment method fees payment method charges Collect Payment processing fees from customer. Fees can be configured as fixed or percentage wise Payment fee Website surcharge Extra payment fees Payment surcharge Minimum order amount fee Product-specific payment fees Additional charges on orders Custom fee rules Configurable payment fees Country-based surcharge Product extra fees Payment Method Surcharge.',
    'description': """Aims to integrate a feature that calculates and displays extra fees based on a percentage associated with specific payment methods in Odoo's eCommerce module.""",
    'author': "Khaled Hassan",
    'website': "https://apps.odoo.com/apps/modules/browse?search=Khaled+hassan",
    'depends': [
        'website_sale'
    ],
    'data': [
        'data/data.xml',
        'views/payment_method.xml',
        'views/templates.xml'
    ],
    'assets': {
        'web.assets_frontend': [
            'website_payment_method_fees/static/src/js/service_fees.js',
            'website_payment_method_fees/static/src/scss/payment_method_fees.scss',
        ]
    },
    'license': 'OPL-1',
    'price': 45,
    'currency': 'EUR',
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'application': True,
}
