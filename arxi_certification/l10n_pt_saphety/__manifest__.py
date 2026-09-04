{
    'name'          : 'Portugal - Saphety Invoice Signature',
    'summary'       : """Signs invoices with Saphety.""",
    'author'        : "ARXILEAD",
    'website'       : "https://www.arxi.pt",
    'category'      : 'Accounting & Finance',
    'version'       : '1.2',
    'license'       : 'OPL-1',
    # l10n_pt_edi_partner_filter was absorbed into this module (see
    # migrations/1.1/pre-merge_edi_partner_filter.py)
    'depends'       : [
        'account_edi',
        'l10n_pt_certificate',
    ],
    'data'          : [
        'security/ir.model.access.csv',
        'data/account_edi_data.xml',
        'data/ir_cron.xml',
        'data/cius_pt_templates.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/product_category_views.xml',
        'views/res_company_views.xml',
        # Absorbed from l10n_pt_edi_partner_filter (Etapa 2.2)
        'views/res_partner_views.xml',
    ],
    'post_init_hook': '_post_init_hook',
}
