{
    'name'       : "Arxi Quality Payroll API Client",
    'sequence'   : 42,
    'license'    : 'OPL-1',
    'summary'    : """Endpoint to communicate with Arxi Quality Tests for Payroll""",

    'author'     : "ARXILEAD",
    'website'    : "https://www.arxi.pt",

    'category'   : 'Manufacturing/Quality',
    'version'    : '19.0.0.0.0',

    'depends'    : [
        'account',
        'sale',
        'l10n_pt_hr_payroll'
    ],
    'data'       : [
        'data/external_identifiers.xml'
    ],

    'installable': True,
}
