{
    'name'        : 'Portugal - Saphety Stock Purchase Request Number',
    'summary'     : """Adds Purchase Request Number in Stock Documents to link with Invoices/Credit Notes.""",
    'author'      : "ARXILEAD",
    'website'     : "https://www.arxi.pt",
    'category'    : 'Accounting & Finance',
    'version'     : '1.0',
    'license'     : 'OPL-1',
    'depends'     : [
        'l10n_pt_saphety_sale_purchase_request_nr',
        'l10n_pt_stock'
    ],
    'data'        : [
        'views/pt_transport_views.xml',
        'views/stock_picking_views.xml',
        'report/stock_picking_report.xml',
        'report/pt_transport_report.xml'
    ],
    'auto_install': True,
}
