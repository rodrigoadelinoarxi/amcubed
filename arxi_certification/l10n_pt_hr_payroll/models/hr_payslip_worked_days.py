from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    # Override fields to remove any check_company or negative constraints
    number_of_days = fields.Float(
        string='Number of Days',
        help="Number of days"
    )
    number_of_hours = fields.Float(
        string='Number of Hours',
        help="Number of hours"
    )

    is_correction = fields.Boolean(
        default=False,
        help="Indicates if this line is a correction from previous periods. "
             "The salary rules determine if it's an addition or deduction based on the work entry type."
    )
    ref_date = fields.Char(
        help="Reference date of the correction in YYYY.MM format"
    )
