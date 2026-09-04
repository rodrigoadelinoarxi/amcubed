{
    "name": "Portugal / Angola - Certified Point of Sale Settle Due",
    "summary": """
        Block POS customer-due settlement in PT/AO (certified invoicing only)""",
    "author": "ARXILEAD",
    "website": "https://www.arxi.pt",
    "category": "Sales/Point Of Sale",
    "version": "1.1",
    "license": "OPL-1",
    "depends": [
        "l10n_pt_ao_pos",
        "pos_settle_due",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_pt_ao_pos_settle_due/static/src/app/**/*",
        ],
    },
    "auto_install": True,
}
