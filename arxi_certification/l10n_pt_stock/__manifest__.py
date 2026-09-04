{
    'name'                 : 'Portugal - Certified Stock',
    'summary'              : """Module for stock certification and exporting SAF-T""",

    'author'               : 'ARXILEAD',
    'website'              : 'https://www.arxi.pt',
    'category'             : 'Warehouse',
    'sequence'             : 151,
     'version'              : '1.8',
    'license'              : 'OPL-1',
    'depends'              : [
        'l10n_pt_certificate', 'l10n_pt_ao', 'stock', 'stock_account', 'stock_sms'
    ],
    'data'                 : [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/account_document_type.xml',
        'views/stock_picking_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/transport_document_views.xml',
        'views/transport_document_journal_views.xml',
        'views/pt_transport_portal_templates.xml',
        'views/product_category_views.xml',
        'views/stock_move_line_views.xml',
        'wizard/stock_quantity_history_views.xml',
        'report/stock_picking_templates.xml',
        'report/transport_document_report.xml',
        # Absorbed from print_conf_copies_pt
        'report/delivery_slip_report.xml',
        'report/picking_operations.xml',
    ],
    'auto_install'         : ['l10n_pt_certificate', 'stock_account'],
    'post_init_hook'       : '_post_init_hook'
}
