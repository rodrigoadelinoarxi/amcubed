{
    'name'          : 'Portugal - Saphety Sale Order Purchase Request Number',
    'summary'       : """Adds Purchase Request Number in Sales to link with Invoices/Credit Notes.""",
    'author'        : "ARXILEAD",
    'website'       : "https://www.arxi.pt",
    'category'      : 'Accounting & Finance',
    'version'       : '1.0',
    'license'       : 'OPL-1',
    'depends'       : [
        'l10n_pt_saphety',
        'sale'
    ],
    'data'          : [
        'data/cius_pt_templates.xml',
        'views/sale_order_views.xml',
        'report/sale_order_report.xml',
        'report/account_move_report.xml'
    ],
}
