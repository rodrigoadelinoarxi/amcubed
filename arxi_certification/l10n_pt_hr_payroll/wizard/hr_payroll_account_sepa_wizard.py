from odoo import fields, models, _
from odoo.exceptions import UserError


class HrPayrollPaymentReportWizard(models.TransientModel):
    _inherit = 'hr.payroll.payment.report.wizard'

    def generate_payment_report(self):
        super(HrPayrollPaymentReportWizard, self.with_context(payslip_sepa=True)).generate_payment_report()
