{
    'name'                 : 'Portugal - Certified Sale Stock',
    'summary'              : """
        Module for sale stock certification and compatibility""",

    'author'               : "ARXILEAD",
    'website'              : "https://www.arxi.pt",
    'category'             : 'Warehouse',
    'version'              : '1.3',
    'license'              : 'OPL-1',
    'depends'              : ['l10n_pt_stock', 'sale_stock', 'l10n_pt_ao_sale'],
    'data'                 : [

        'views/sale_order_views.xml',
    ],
    'auto_install'         : ['l10n_pt_stock', 'sale_stock'],
}
