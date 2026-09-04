{
    'name'                 : 'Portugal - Import Bills from E-Fatura ',
    'version'              : '18.0.0.0.2',
    'category'             : 'Accounting/Localizations/Account Charts',
    'license'              : 'OPL-1',
    'author'               : 'ARXILEAD',
    'website'              : 'https://arxi.pt',
    'summary'              : 'Portuguese E-Fatura Integration - Tax Authority Electronic Invoicing',

    'description'          : """
Portuguese E-Fatura Integration
================================

This module integrates Odoo with the Portuguese Tax Authority's E-Fatura system.

Features:
---------
* Import E-Fatura documents via online synchronization
* Automatic vendor bill creation/update from E-Fatura
* E-Fatura document status tracking
* Mismatch detection between Odoo and E-Fatura amounts
* Tax mapping configuration
* Multi-company support with enable/disable per company

Requirements:
-------------
* Odoo 18.0
* Portuguese localization
* Tax Authority credentials for online sync
* Python dependencies: beautifulsoup4, html5lib, requests

Configuration:
--------------
1. Enable E-Fatura integration in Settings > Accounting
2. Configure Tax Authority credentials in company settings
3. Set up default E-Fatura journal
4. Configure tax mappings per partner or globally

Usage:
------
* Import E-Fatura: Accounting > E-Fatura > Import E-Fatura
* Select date range and click Import to sync with Tax Authority portal

    """,

    'depends'              : [
        'account',
        'base',
        'mail',
    ],

    'external_dependencies': {
        'python': [
            'beautifulsoup4',
            'html5lib',
            'requests',
        ],
    },

    'data'                 : [
        # Security
        'security/ir.model.access.csv',
        'security/efatura_security.xml',

        # Views
        'views/l10n_pt_account_efatura.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/res_config_views.xml',

        # Wizards
        'wizards/l10n_pt_dataport_import_efatura.xml',
    ],

    'assets'               : {
        'web.assets_backend': [
            'l10n_pt_efatura_import/static/src/js/efatura_tree_extend.js',
            'l10n_pt_efatura_import/static/src/xml/efatura_list_button.xml',
        ],
    },
    'installable'          : True,
    'auto_install'         : False,
    'application'          : False,
}
