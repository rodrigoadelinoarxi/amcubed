{
    'name': "Vies Integration",
    'summary': """Adds all existing partner info from the VIES Web Service. Inpu a valid NIF in a new Partner, click always and the module will automatically fill the partner info with the VIES Web Service data.""",
    'author': "ARXILEAD",
    'website': "http://www.arxi.pt",
    'category': 'Accounting',
    'version': '17.0.0.0.0',
    'depends': ['base'],
    'license': 'OPL-1',
    'sequence': 200,
    'external_dependencies': {
        'python': ['stdnum', 'zeep'],
    }
}
