{
    'name': "Vies Integration",
    'summary': """Adds all existing partner info from the VIES Web Service""",
    'author': "ARXILEAD",
    'website': "http://www.arxi.pt",
    'category': 'Accounting',
    'version': '1.0',
    'depends': [
        'base',
        'l10n_pt_ao'
    ],
    'auto_install': True,
    'license': 'OPL-1',
    'sequence': 200,
    'external_dependencies': {
        'python': ['python-stdnum', 'zeep'],
    }
}
