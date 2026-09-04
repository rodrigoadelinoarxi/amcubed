from odoo import models, fields


class IrsTaxTable(models.Model):
    _name = 'irs.tax.table'
    _description = 'IRS Tax Table Model'

    name = fields.Char(string="Name", translate=True)
    code = fields.Char(string="code")
    table_line_ids = fields.One2many('irs.tax.table.line', 'table_id')
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")
    income_locale = fields.Selection([
        ('C', 'Continent'),
        ('RA', 'Autonomous Region of Azores'),
        ('RM', 'Autonomous Region of Madeira'),
        ('E', 'Foreign Country'),
    ], default='C')
    category = fields.Selection([
        ('A', 'Category A'),
        ('H', 'Category H'),
    ], string="Income Category", default='A')


class IrsTaxTableLine(models.Model):
    _name = 'irs.tax.table.line'
    _description = 'IRS Tax Table Line'

    table_id = fields.Many2one('irs.tax.table')
    value = fields.Float(string="Monthly Wage")
    marginal_rate = fields.Float(string="Marginal Rate", digits=(4, 4))
    to_be_deducted = fields.Char(string="Portion to be Deducted")
    dependent_val = fields.Float(string="Portion to Deduct per Dependent")
