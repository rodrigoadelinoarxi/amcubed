{
    "name": "Portugal / Angola - Certified Point of Sale and Loyalty Program",
    "summary": """
        Module for POS certification and Loyalty Program""",
    "author": "ARXILEAD",
    "website": "https://www.arxi.pt",
    "category": "Sales/Point Of Sale",
    "version": "1.2",
    "license": "OPL-1",
    "depends": ["l10n_pt_ao_pos", "pos_loyalty"],
    "data": [
        "views/pos_config_views.xml",
        "views/pos_loyalty_views.xml",
        "views/product_views.xml",
        "views/res_partner_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_pt_ao_pos_loyalty/static/src/js/**/*",
        ],
    },
}
