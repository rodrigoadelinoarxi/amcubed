from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    l10n_pt_ir_model_data = env['ir.model.data'].search([
        ('module', '=', 'l10n_pt_certificate'),
        ('model', '=', 'account.fiscal.position.tax.template')
    ])

    for ir_model_data in l10n_pt_ir_model_data:
        env['account.fiscal.position.tax.template'].browse(ir_model_data.res_id).unlink()

    l10n_pt_ir_model_data.unlink()
