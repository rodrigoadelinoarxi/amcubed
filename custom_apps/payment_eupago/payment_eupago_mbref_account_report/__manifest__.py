{
    'name'          : 'euPago MbRef Payment Acquirer Account Report',
    'summary'       : 'Payment Acquirer: euPago MbRef Implementation Account Report',
    'author'        : 'Arxi',
    'website'       : 'http://www.arxi.pt',
    'category'      : 'Payment Acquirer',
    'version'       : '19.0.0.0.2',
    'license'       : 'OPL-1',
    'depends'       : [
        'payment_eupago_mbref', 'account'
    ],
    'data'          : [
        'reports/account_invoice_mbref_report.xml',
    ],
    'installable'   : True,
}
