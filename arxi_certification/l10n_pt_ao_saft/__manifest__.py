{
    'name': 'SAF-T',
    'summary': """
        Module for SAF-T""",

    'author': "ARXILEAD",
    'website': "https://www.arxi.pt",
    'category': 'Accounting & Finance',
    'version': '1.0',
    'license': 'OPL-1',
    'depends': ['l10n_pt_ao'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/saft_import_wizard_views.xml',
    ],
    'assets': {
    },
    'auto_install': ['l10n_pt_ao'],
}
