{
    'name': 'Display Total Discount',
    'summary': """
        Module responsible for implementing Global Discount in the sales
    """,

    'author': "ARXILEAD",
    'website': 'https://www.arxi.pt',
    'category': 'Accounting & Finance',
    'version': '1.2',
    'license': 'OPL-1',
    'depends': ['delivery', 'sale', 'account'],
    'data': [
        'data/global_discount_data.xml',
        'views/sale_order_views.xml',
        'views/account_move_views.xml',
        'report/sale_order_templates.xml',
    ],
}
