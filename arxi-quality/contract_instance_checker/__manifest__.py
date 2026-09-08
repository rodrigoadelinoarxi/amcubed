# -*- coding: utf-8 -*-
{
    "name": "Contract Instance Checker",
    "version": "19.0.2.1.8",
    "category": "Services/Contract",
    "summary": "Automatic contract validation for controlled instances",
    "description": """
Module for installation on controlled instances that automatically validates
the contract with the central system.

Features:

* Automatic daily validation with central system via API
* Visual alerts when contract is approaching expiration
* Automatic instance blocking when contract expires
* User limit controls
* Alerts when number of users exceeds the limit
* Simple configuration via Settings (NIF, Token, Central URL)
* Tamper-proof security system
    """,
    "author": "FlyByOdoo",
    "website": "https://www.flybyodoo.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "sale",
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/instance_checker_cron.xml",
        "views/res_config_settings_views.xml",
        "views/contract_status_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "contract_instance_checker/static/src/scss/contract_alert.scss",
            "contract_instance_checker/static/src/scss/contract_banner.scss",
            "contract_instance_checker/static/src/js/contract_banner.js",
            "contract_instance_checker/static/src/xml/contract_banner.xml",
        ],
    },
    "demo": [],
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
