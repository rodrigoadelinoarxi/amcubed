from odoo import models, fields, api, _


class SsRegime(models.Model):
    _name = 'ss.regime'
    _description = 'Social Security Regimes'

    name = fields.Char(translate=True)
    employer_rate = fields.Float()
    employee_rate = fields.Float()
