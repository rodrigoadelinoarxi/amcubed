# -*- encoding: utf-8 -*-

{
    'name'       : 'Portuguese Payroll Unique Report',
    'category'   : 'Localization/Payroll',
    'author'     : 'ARXILEAD',
    'website'    : 'http://arxi.pt/',
    'depends'    : [
        'l10n_pt_hr_payroll',
    ],
    'version'    : '19.0.0.0.3',
    'license'    : 'OPL-1',
    'description': """
    """,
    'data'       : [
        # Security
        'security/ir.model.access.csv',

        # Data
        'data/unique.report.table.3.csv',
        'data/unique.report.table.4.csv',
        'data/unique.report.table.5.csv',
        'data/unique.report.table.6.csv',
        'data/unique.report.table.7.csv',
        'data/unique.report.table.8.csv',
        'data/unique.report.table.9.csv',
        'data/unique.report.table.10.csv',
        'data/unique.report.table.11.csv',
        'data/unique.report.table.13.csv',
        'data/unique.report.table.14.csv',
        'data/unique.report.table.15.csv',
        'data/unique.report.table.16.csv',
        'data/unique.report.table.19.csv',
        'data/unique.report.table.21.csv',
        'data/unique.report.table.22.csv',
        'data/unique.report.table.23.csv',
        'data/unique.report.table.24.csv',
        'data/unique.report.table.25.csv',
        'data/unique.report.table.26.csv',
        'data/unique.report.table.27.csv',
        'data/unique.report.table.28.csv',
        'data/unique.report.table.29.csv',
        'data/unique.report.table.30.csv',
        'data/unique.report.table.31.csv',
        'data/unique.report.table.32.csv',
        'data/unique.report.table.33.csv',
        'data/unique.report.table.34.csv',
        'data/unique.report.table.35.csv',
        'data/unique.report.table.36.csv',
        'data/unique.report.table.52.csv',
        'data/unique.report.table.53.csv',
        'data/unique_report_annex_0_file.xml',
        'data/unique_report_annex_a_file.xml',
        'data/unique_report_annex_b_file.xml',
        'data/unique_report_annex_c_file.xml',
        'data/unique_report_annex_e_file.xml',

        # Views
        'views/unique_report_views.xml',
        'views/res_company_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_leave_views.xml',
        'views/hr_leave_type_views.xml',

        # Wizard
        'wizard/unique_report_export_views.xml',

    ],
}
