from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _


class HrSalaryAttachment(models.Model):
    _inherit = 'hr.salary.attachment'

    deduction_type = fields.Selection([
        ('AWARD', 'Award'),
        ('ADVANCE', 'Advance'),
        ('KM', 'Kms Own Vehicle'),
        ('AC', 'Allowance Cost'),
        ('BAL_BONUS', 'Balance Sheet Bonus'),
        ('COMISSION', 'Commissions'),
        ('COMP_SUB_EDU', 'Sub Comp Enc Education'),
        ('EXP_EDU', 'Education Expenses'),
        ('CHILD_VAL', 'Childhood Valley'),
        ('FAIL_ALLOW', 'Fail Allowance'),
        ('RET_PLAN', 'Retirement Savings Plan'),
        ('VAC_ALLW', 'Vacation Allowance'),
        ('CHR_ALLW', 'Christmas Allowance'),
        ('TN', 'Night Work'),
        ('HD', 'Sunday Hours'),
    ], string="Deduction Type",
        ondelete={
            'AWARD'       : lambda r: r.write({'type': 'attachment'}),
            'ADVANCE'     : lambda r: r.write({'type': 'attachment'}),
            'KM'          : lambda r: r.write({'type': 'attachment'}),
            'AC'          : lambda r: r.write({'type': 'attachment'}),
            'BAL_BONUS'   : lambda r: r.write({'type': 'attachment'}),
            'COMISSION'   : lambda r: r.write({'type': 'attachment'}),
            'COMP_SUB_EDU': lambda r: r.write({'type': 'attachment'}),
            'EXP_EDU'     : lambda r: r.write({'type': 'attachment'}),
            'CHILD_VAL'   : lambda r: r.write({'type': 'attachment'}),
            'FAIL_ALLOW'  : lambda r: r.write({'type': 'attachment'}),
            'RET_PLAN'    : lambda r: r.write({'type': 'attachment'}),
            'VAC_ALLW'    : lambda r: r.write({'type': 'attachment'}),
            'CHR_ALLW'    : lambda r: r.write({'type': 'attachment'}),
            'TN'          : lambda r: r.write({'type': 'attachment'}),
            'HD'          : lambda r: r.write({'type': 'attachment'}),
        })
