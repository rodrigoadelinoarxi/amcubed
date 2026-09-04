{
    "name": "Portugal / Angola - Certified Point of Sale",
    "summary": """
        Module for POS certification and exporting SAF-T""",
    "author": "ARXILEAD",
    "website": "https://www.arxi.pt",
    "category": "Sales/Point Of Sale",
    "version": "1.14",
    "license": "OPL-1",
    "depends": [
        "l10n_pt_ao",
        "point_of_sale",
    ],
    "data": [
        "report/account_move_templates.xml",
        "views/res_config_settings_views.xml",
        "views/pos_config_views.xml",
        "views/product_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_pt_ao_pos/static/src/js/**/*",
            "l10n_pt_ao_pos/static/src/xml/**/*",
            "l10n_pt_ao_pos/static/src/css/**/*",
        ],
        "web.assets_tests": [
            "l10n_pt_ao_pos/static/tests/tours/**/*",
        ],
    },
    "auto_install": True,
    "post_init_hook": "_disable_ticket_qr_code",
}
