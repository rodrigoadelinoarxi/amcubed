{
    'name'       : "Arxi Quality SAFT API Client",
    'sequence'   : 42,
    'license'    : 'OPL-1',
    'summary'    : """Endpoint to communicate with Arxi Quality Tests""",

    'author'     : "ARXILEAD",
    'website'    : "https://www.arxi.pt",

    'category'   : 'Manufacturing/Quality',
    'version'    : '2.0.4',

    'depends'    : [
        'account',
        'sale',
        'l10n_pt_certificate',
    ],
    'data'       : [
        'data/external_identifiers.xml'
    ],

    'installable': True,
}
