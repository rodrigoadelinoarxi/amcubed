{
    "name": "Portugal - Certified Invoicing",
    "summary": """
        Module for certified invoicing and exporting SAF-T""",
    "author": "ARXILEAD",
    "website": "https://www.arxi.pt",
    "category": "Accounting/Localizations/Account Charts",
    "sequence": 150,
    "version": "1.49",
    "license": "OPL-1",
    # l10n_pt_arxi_coa was absorbed into this module (see
    # migrations/1.43/pre-merge_arxi_coa.py); sh_message was replaced by the
    # native display_notification helper in account_series.py
    "depends": [
        "l10n_pt_ao",
        "account",
        "account_debit_note",
        "l10n_pt_ao_access",
        "l10n_pt_ao_saft",
    ],
    "external_dependencies": {
        "python": ["pycryptodome", "xmlschema", "pdftotext", "zeep"],
    },
    "data": [
        # Security
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "security/res_groups.xml",
        # Data
        "data/account_tax_exemption.xml",
        "data/account_taxonomy_data.xml",
        "data/document_status_type.xml",
        "data/income_data.xml",
        "data/config_param.xml",
        "data/ir_config_action.xml",
        "data/res_partner_data.xml",
        "data/account_document_type.xml",
        "data/saft_template.xml",
        "data/ubl_templates_cius_pt.xml",
        "data/res.lang.csv",
        "data/mail_template.xml",
        # Absorbed from l10n_pt_arxi_coa (Bloco A da migração v19)
        "data/account_tax_report.xml",
        # Report
        "report/account_move_templates.xml",
        "report/report_templates.xml",
        "report/account_payment_templates.xml",
        "report/account_self_billing_template.xml",
        "data/protected_reports_data.xml",
        # Views
        "views/account_move_views.xml",
        "views/account_journal_views.xml",
        "views/account_payment_views.xml",
        "views/res_company_views.xml",
        "views/account_tax_views.xml",
        "views/account_series_views.xml",
        "views/res_config_settings_views.xml",
        "views/account_income_type_views.xml",
        "views/account_income_location_views.xml",
        "views/account_taxonomy.xml",
        "views/res_partner_views.xml",
        "views/l10n_pt_certificate_menus.xml",
        "views/account_account.xml",
        "views/uom_uom_views.xml",
        # Wizard
        "wizard/account_payment_views.xml",
        "wizard/saft_wizard_views.xml",
        "wizard/account_series_wizard_views.xml",
        "wizard/update_tax_grid_wizard_views.xml",
        "wizard/account_debit_note_views.xml",
    ],
    "demo": [
        "demo/demo_company.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "l10n_pt_certificate/static/src/scss/reports.scss",
        ],
    },
    "pre_init_hook": "_pre_init_hook",
    "post_init_hook": "_post_init_hook",
}
