from odoo import models, fields, api, _


class SalaryRule(models.Model):
    _name = 'hr.salary.rule'
    _inherit = ['hr.salary.rule', 'mail.thread']

    name = fields.Char(required=True, translate=True, tracking=True)
    code = fields.Char(required=True,
                       help="The code of salary rules can be used as reference in computation of other rules. "
                            "In that case, it is case sensitive.", tracking=True)
    struct_id = fields.Many2one('hr.payroll.structure', string="Salary Structure", required=True, tracking=True)
    category_id = fields.Many2one(tracking=True)
    income_type = fields.Char(tracking=True)
    exempt_income_type = fields.Char(tracking=True)
    ss_code = fields.Char(tracking=True)
    other_benefits = fields.Boolean(default=False, tracking=True)
    in_insurance_map = fields.Boolean(default=False, string="Present in Insurance Map", tracking=True)
    used_in_entries = fields.Boolean(default=True, string="Used in Accounting Entries", tracking=True)
    insurance_code = fields.Char(tracking=True)
    show_qty_in_pdf = fields.Boolean(string="Show Quantity in Slip", default=False, tracking=True)
    skip_compute = fields.Boolean(string="Skip Compute", default=False, tracking=True)
    is_retroactive = fields.Boolean(string="Is Retroactive", default=False, tracking=True)
    retroactive_type = fields.Selection([
        ('wage', 'Wage'),
        ('allowance', 'Allowance'),
        ('absence', 'Absence / Deduction'),
        ('extra_hours', 'Extra Hours'),
        ('manual', 'Manual'),
    ], tracking=True)
    original_rule_id = fields.Many2one('hr.salary.rule', string="Original Corrected Rule", tracking=True)
    retroactive_input_type_id = fields.Many2one(
        'hr.payslip.input.type',
        string="Retroactive Input Type",
        domain=[('is_retroactive', '=', True)],
        tracking=True,
    )
    allow_negative = fields.Boolean(string="Allow Negative Value", default=False, tracking=True)
    natrem_code = fields.Char(string="NATREM Code", tracking=True)
    use_origin_month_for_dri = fields.Boolean(string="Use Origin Month in DRI", default=True, tracking=True)
    in_dmr = fields.Boolean(string="Included in DMR", default=False, tracking=True)
    in_dri = fields.Boolean(string="Included in DRI", default=False, tracking=True)
    in_accounting = fields.Boolean(string="Included in Accounting", default=False, tracking=True)
