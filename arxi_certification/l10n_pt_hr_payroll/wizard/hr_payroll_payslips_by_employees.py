from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import format_date, float_round


class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    contract_type = fields.Many2one('hr.contract.type')

    payslip_run_id = fields.Many2one('hr.payslip.run', default=lambda self: self._default_payslip_run_id())
    payslip_run_type = fields.Selection(related='payslip_run_id.payslip_type')
    extraordinary_rubric = fields.Selection(related='payslip_run_id.extraordinary_rubric')
    bonus_application_rule = fields.Selection(related='payslip_run_id.bonus_application_rule')
    bonus_value_type = fields.Selection(related='payslip_run_id.bonus_value_type')
    extraordinary_line_ids = fields.One2many('hr.payslip.employees.line', 'wizard_id', string='Bonus Values',
                                             compute='_compute_extraordinary_line_ids', store=True, readonly=False)
    extraordinary_eligibility_info = fields.Text(compute='_compute_extraordinary_eligibility_info')

    def _default_payslip_run_id(self):
        if self.env.context.get('active_model') == 'hr.payslip.run':
            return self.env.context.get('active_id')
        return False

    def default_get(self, fields_list):
        # The 'employee_ids' field inherited from hr.payroll has its own
        # default (an unfiltered search), which is applied before
        # _compute_employee_ids ever runs, so its extraordinary-batch
        # eligibility filter is bypassed on the initial values of a new
        # wizard. Re-apply the filter here so the wizard doesn't open
        # pre-selecting employees that can't be part of the batch.
        res = super().default_get(fields_list)
        if 'employee_ids' in res and res['employee_ids']:
            run = self.env['hr.payslip.run'].browse(self._default_payslip_run_id())
            if run and run.payslip_type == 'extraordinary':
                # x2many defaults come back as [(6, 0, ids)] commands.
                employee_ids = res['employee_ids'][0][2] if isinstance(res['employee_ids'][0], (list, tuple)) \
                    else res['employee_ids']
                employees = self.env['hr.employee'].browse(employee_ids)
                contracts = employees._get_contracts(run.date_start, run.date_end)
                eligible = employees.filtered(
                    lambda e: not run._get_extraordinary_ineligible_reason(
                        e, contracts[e.id][:1]))
                res['employee_ids'] = [(6, 0, eligible.ids)]
        return res

    @api.depends('department_id', 'contract_type', 'payslip_run_id')
    def _compute_employee_ids(self):
        for wizard in self:
            domain = wizard._get_available_contracts_domain()
            if wizard.department_id:
                domain = expression.AND([
                    domain,
                    [('department_id', 'child_of', self.department_id.id)]
                ])
            if wizard.contract_type:
                domain = expression.AND([
                    domain,
                    [('version_id.contract_type_id', '=', self.contract_type.id)]
                ])
            employees = self.env['hr.employee'].search(domain)
            run = wizard.payslip_run_id
            if run and run.payslip_type == 'extraordinary':
                employees = employees.filtered(
                    lambda e: not run._get_extraordinary_ineligible_reason(e, wizard._get_run_contract(e)))
            wizard.employee_ids = employees

    def _get_run_contract(self, employee):
        run = self.payslip_run_id
        return employee._get_contracts(run.date_start, run.date_end)[employee.id][:1]

    @api.depends('employee_ids', 'payslip_run_id')
    def _compute_extraordinary_line_ids(self):
        for wizard in self:
            run = wizard.payslip_run_id
            if not (run and run.payslip_type == 'extraordinary' and run.extraordinary_rubric == 'bonus'
                    and run.bonus_application_rule == 'per_employee'):
                wizard.extraordinary_line_ids = [(5, 0, 0)]
                continue
            commands = []
            existing = {line.employee_id.id: line for line in wizard.extraordinary_line_ids}
            for employee in wizard.employee_ids:
                if employee.id not in existing:
                    commands.append((0, 0, {
                        'employee_id': employee.id,
                        'version_id': wizard._get_run_contract(employee).id,
                    }))
            for employee_id, line in existing.items():
                if employee_id not in wizard.employee_ids.ids:
                    commands.append((2, line.id))
            wizard.extraordinary_line_ids = commands

    @api.depends('department_id', 'contract_type', 'payslip_run_id')
    def _compute_extraordinary_eligibility_info(self):
        for wizard in self:
            run = wizard.payslip_run_id
            if not (run and run.payslip_type == 'extraordinary'):
                wizard.extraordinary_eligibility_info = False
                continue
            domain = wizard._get_available_contracts_domain()
            if wizard.department_id:
                domain = expression.AND([domain, [('department_id', 'child_of', wizard.department_id.id)]])
            if wizard.contract_type:
                domain = expression.AND([domain, [('version_id.contract_type_id', '=', wizard.contract_type.id)]])
            reasons = []
            for employee in self.env['hr.employee'].search(domain):
                reason = run._get_extraordinary_ineligible_reason(employee, wizard._get_run_contract(employee))
                if reason:
                    reasons.append('%s: %s' % (employee.name, reason))
            wizard.extraordinary_eligibility_info = '\n'.join(reasons) if reasons else False

    def _get_bonus_amount(self, contract):
        run = self.payslip_run_id
        if run.bonus_application_rule == 'general':
            if run.bonus_value_type == 'fixed':
                return run.bonus_general_amount
            return float_round(contract.wage * run.bonus_general_percentage, precision_digits=2)
        line = self.extraordinary_line_ids.filtered(lambda l: l.employee_id == contract.employee_id)[:1]
        if run.bonus_value_type == 'fixed':
            return line.amount
        return float_round(contract.wage * line.percentage, precision_digits=2)

    def _check_extraordinary_generation(self, employees):
        self.ensure_one()
        run = self.payslip_run_id
        run._check_extraordinary_config()
        errors = []
        for employee in employees:
            reason = run._get_extraordinary_ineligible_reason(employee, self._get_run_contract(employee))
            if reason:
                errors.append('%s: %s' % (employee.name, reason))
        if errors:
            raise ValidationError(
                _('The following employees cannot be included in the extraordinary batch:')
                + '\n' + '\n'.join(errors))
        if run.extraordinary_rubric == 'bonus' and run.bonus_application_rule == 'per_employee':
            lines_by_employee = {line.employee_id: line for line in self.extraordinary_line_ids}
            for employee in employees:
                line = lines_by_employee.get(employee)
                if run.bonus_value_type == 'fixed' and not (line and line.amount):
                    raise ValidationError(_(
                        'There are employees without a defined value. '
                        'Fill in all the values before generating the batch.'))
                if run.bonus_value_type == 'percentage' and not (line and line.percentage):
                    raise ValidationError(_(
                        'There are employees without a defined percentage or without a valid base wage. '
                        'It is not possible to generate the batch.'))

    def compute_sheet(self):
        self.ensure_one()
        run = self.payslip_run_id
        if not run or run.payslip_type != 'extraordinary':
            return super().compute_sheet()

        employees = self.with_context(active_test=False).employee_ids - run.slip_ids.employee_id
        self._check_extraordinary_generation(employees)
        existing_slips = run.slip_ids
        res = super(HrPayslipEmployees, self.with_context(default_payslip_type='extraordinary')).compute_sheet()
        new_slips = run.slip_ids - existing_slips
        if run.extraordinary_rubric == 'bonus' and new_slips:
            input_type = self.env.ref('l10n_pt_hr_payroll.hr_rule_input_perf_bonus')
            self.env['hr.payslip.input'].create([{
                'payslip_id': slip.id,
                'input_type_id': input_type.id,
                'name': run.name,
                'code': input_type.code,
                'amount': self._get_bonus_amount(slip.version_id),
            } for slip in new_slips])
            new_slips.compute_sheet()
        return res

    def _filter_contracts(self, contracts):
        contracts = super()._filter_contracts(contracts)
        run = self.payslip_run_id
        if run and run.payslip_type == 'extraordinary':
            contracts = contracts.filtered(
                lambda c: not run._get_extraordinary_ineligible_reason(c.employee_id, c))
        return contracts


class HrPayslipEmployeesLine(models.TransientModel):
    _name = 'hr.payslip.employees.line'
    _description = 'Extraordinary Batch Employee Value'

    wizard_id = fields.Many2one('hr.payslip.employees', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', required=True)
    version_id = fields.Many2one('hr.version')
    currency_id = fields.Many2one(related='version_id.currency_id')
    wage = fields.Monetary(related='version_id.wage', string='Base Wage')
    bonus_value_type = fields.Selection(related='wizard_id.bonus_value_type')
    amount = fields.Monetary(string='Value', currency_field='currency_id')
    percentage = fields.Float(string='Percentage')
    total = fields.Monetary(string='Value to Pay', compute='_compute_total', currency_field='currency_id')

    @api.depends('amount', 'percentage', 'wage', 'bonus_value_type')
    def _compute_total(self):
        for line in self:
            if line.bonus_value_type == 'percentage':
                line.total = float_round(line.wage * line.percentage, precision_digits=2)
            else:
                line.total = line.amount
