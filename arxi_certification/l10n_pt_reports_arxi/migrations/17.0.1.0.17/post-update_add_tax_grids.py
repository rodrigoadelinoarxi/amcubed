from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    minus_dp_iva40 = env['account.account.tag'].search([('name', '=', '-dp_iva[40]'), ('country_id', '=', env.ref('base.pt').id)])
    a = env['account.tax'].search([]).filtered(
        lambda r: r.refund_repartition_line_ids.filtered(lambda val: minus_dp_iva40.id in val.tag_ids.ids))
    for rec in a:
        for s in rec.refund_repartition_line_ids:
            if s.repartition_type == 'base':
                s.write({'tag_ids': [(4, env.ref('l10n_pt_reports_arxi.base40negative').id)]})
    # +dp_iva[40]  53
    # +dp_base[40] 315
    plus_dp_iva40 = env['account.account.tag'].search([('name', '=', '+dp_iva[40]'),('country_id', '=', env.ref('base.pt').id)])
    b = env['account.tax'].search([]).filtered(
        lambda r: r.refund_repartition_line_ids.filtered(lambda val: plus_dp_iva40.id in val.tag_ids.ids))
    for rec in b:
        for s in rec.refund_repartition_line_ids:
            if s.repartition_type == 'base':
                s.write({'tag_ids': [(4, env.ref('l10n_pt_reports_arxi.base40positive').id)]})
    # #-dp_iva[41]
    minus_dp_iva41 = env['account.account.tag'].search([('name', '=', '-dp_iva[41]'),('country_id', '=', env.ref('base.pt').id)])
    c = env['account.tax'].search([]).filtered(
        lambda r: r.refund_repartition_line_ids.filtered(lambda val: minus_dp_iva41.id in val.tag_ids.ids))
    for rec in c:
        for s in rec.refund_repartition_line_ids:
            if s.repartition_type == 'base':
                s.write({'tag_ids': [(4, env.ref('l10n_pt_reports_arxi.base41negative').id)]})
    # #+dp_iva[41]
    plus_dp_iva41 = env['account.account.tag'].search([('name', '=', '+dp_iva[41]'),('country_id', '=', env.ref('base.pt').id)])
    d = env['account.tax'].search([]).filtered(
        lambda r: r.refund_repartition_line_ids.filtered(lambda val: plus_dp_iva41.id in val.tag_ids.ids))
    for rec in d:
        for s in rec.refund_repartition_line_ids:
            if s.repartition_type == 'base':
                s.write({'tag_ids': [(4, env.ref('l10n_pt_reports_arxi.base41positive').id)]})