{
    'name': 'Custom Website Sale Stock',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Override website_sale_stock translations',
    'author': "Arxi",
    'website': "https://www.arxi.pt",
    'depends': [
        'website_sale_stock',
    ],
    'assets': {
        'web.assets_frontend': [
            'custom_website_sale_stock/static/src/xml/product_availability.xml',
            'custom_website_sale_stock/static/src/js/variant_mixin.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
