from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    env.ref('l10n_pt_certificate.pt_chart_template').write({
        'default_cash_difference_income_account_id': env.ref('l10n_pt_certificate.chart_78881').id,
        'default_cash_difference_expense_account_id': env.ref('l10n_pt_certificate.chart_68881').id,
    })
