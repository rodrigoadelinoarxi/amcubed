{
    'name'          : 'Portugal - Saphety Invoice Signature with Transport Documents',
    'summary'       : """Connection between Invoices and Transport Documents for EDI.""",
    'author'        : "ARXILEAD",
    'website'       : "https://www.arxi.pt",
    'category'      : 'Accounting & Finance',
    'version'       : '1.0',
    'license'       : 'OPL-1',
    'depends'       : [
        'l10n_pt_saphety',
        'l10n_pt_stock'
    ],
    'data'          : [
        'data/cius_pt_templates.xml',
        'views/account_move_views.xml',
    ],
}
