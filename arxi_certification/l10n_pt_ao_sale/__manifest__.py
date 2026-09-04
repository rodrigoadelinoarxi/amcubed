{
    'name': 'Sale  - Portugal / Angola',
    'summary': """
        Module for common sale requirements between Portuguese and Angolan localizations""",
    'author': "ARXILEAD",
    'website': "https://www.arxi.pt",
    'category': 'Accounting & Finance',
    'version': '1.23',
    'license': 'OPL-1',
    'depends': ['l10n_pt_ao', 'sale_management', 'product_matrix'],
    'external_dependencies' : {
    },
    'data': [
        # Absorbed from sale_journals: security and the sale.order.type data must
        # load before the views/menus/actions that reference them.
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'security/res_groups.xml',
        'data/sale_order_data.xml',
        'data/account_document_type.xml',
        'data/sale_order_type.xml',
        'views/sale_order_type_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_journal_views.xml',
        'views/sale_journals_menus.xml',
        'views/account_move_views.xml',
        'report/sale_order_templates.xml',
        'report/sale_order_reports.xml',
        'wizard/sale_order_cancel_views.xml',
        'wizard/mass_cancel_orders_views.xml',
        'wizard/sale_order_alert_wizard_views.xml',
        'wizard/sale_make_invoice_advance_views.xml'
    ],
    'demo': [
    ],
    'assets': {

    },
    'auto_install': ['l10n_pt_ao', 'sale_management'],
    # sale.order.option was dropped by Odoo in v19 (optional products on
    # quotations are gone from the core): the SaleOrderOption override, its
    # view xpath and the "Optional Products" report page were removed with it.
    'installable': True,
    'post_init_hook': 'post_init_hook'
}
