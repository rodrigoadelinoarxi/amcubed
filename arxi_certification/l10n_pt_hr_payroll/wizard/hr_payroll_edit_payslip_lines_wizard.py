from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrPayrollEditPayslipLinesWizard(models.TransientModel):
    _inherit = 'hr.payroll.edit.payslip.lines.wizard'

    def action_validate_edition(self):
        res = super(HrPayrollEditPayslipLinesWizard, self).action_validate_edition()

        # Validate negative values only for PT structures
        # Allow negative values for:
        # 1. Deduction lines (category_id.code == 'DED')
        # 2. Correction salary rules (specific rules only)
        if self.payslip_id.company_id and self.payslip_id.company_id.country_id and self.payslip_id.company_id.country_id.code == 'PT':
            correction_rules = [
                self.env.ref('l10n_pt_hr_payroll.hr_payroll_rules_base_correction', raise_if_not_found=False),
                self.env.ref('l10n_pt_hr_payroll.hr_payroll_rules_meal_allw_correction', raise_if_not_found=False),
                self.env.ref('l10n_pt_hr_payroll.hr_payroll_rules_vac_allw_correction', raise_if_not_found=False),
                self.env.ref('l10n_pt_hr_payroll.hr_payroll_rules_chr_allw_correction', raise_if_not_found=False),
            ]
            correction_rule_ids = [rule.id for rule in correction_rules if rule]

            invalid_negative_lines = []
            for line in self.payslip_id.line_ids:
                if line.total < 0:
                    # Check if it's allowed to be negative
                    is_deduction = line.category_id.code == 'DED'
                    is_correction = line.salary_rule_id and line.salary_rule_id.id in correction_rule_ids

                    if not (is_deduction or is_correction):
                        invalid_negative_lines.append(line.name)

            if invalid_negative_lines:
                raise UserError(
                    _('Payslip cannot have negative values on lines that are not deductions or corrections.\n'
                      'Invalid lines: %s') % ', '.join(invalid_negative_lines)
                )

        return res


class HrPayrollEditPayslipLine(models.TransientModel):
    _inherit = 'hr.payroll.edit.payslip.line'

    @api.depends('quantity', 'amount', 'rate')
    def _compute_total(self):
        super(HrPayrollEditPayslipLine, self)._compute_total()
        for line in self.filtered(lambda l: l.salary_rule_id and l.salary_rule_id.skip_compute):
            line.total = line.slip_id.line_ids.filtered(lambda l: l.salary_rule_id.code == line.code).total
