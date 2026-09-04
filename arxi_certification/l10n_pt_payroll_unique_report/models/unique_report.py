from odoo import models, fields, api, _
import calendar
import math
import datetime
from collections import defaultdict
import xmlschema
import base64
import os
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UniqueReport(models.Model):
    _name = 'unique.report'
    _description = 'Unique Report'

    name = fields.Char(string='Name', default='Unique Report')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    xml_file = fields.Binary("XML File")
    xml_filename = fields.Char("XML Filename")

    # Common fields
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    company_vat = fields.Char(related='company_id.vat', string='Company VAT', readonly=True)
    company_niss = fields.Char(related='company_id.niss', string='Company NISS', readonly=True)
    local_unit_number = fields.Char(string='Local Unit Number', related='company_id.local_unit_number', readonly=False)
    reference_year = fields.Char(string='Reference Year', default=lambda self: fields.Date.today().year)

    # Annex 0 Fields

    company_status = fields.Many2one('unique.report.table.5', string='Company Status', readonly=False)
    company_status_reason = fields.Many2one('unique.report.table.6', string='Company Status Reason', readonly=False)
    company_status_reason_visible = fields.Boolean(string='Company Status Reason Visible', default=False,
                                                   compute='_compute_company_status_reason_visible')
    company_status_start_date = fields.Date(string='Company Status Start Date', readonly=False)
    company_status_end_date = fields.Date(string='Company Status End Date', readonly=False)
    incorporation_date = fields.Date(string='Incorporation Date', readonly=False)
    employees_in_service_december = fields.Integer(string='Employees in Service on 31st December', readonly=False,
                                                   compute='_compute_employees_in_service_december')
    employee_in_service_december_avg = fields.Integer(string='Employee in Service on 31st December Average',
                                                      readonly=False,
                                                      compute='_compute_employee_in_service_december_avg')
    deslocated_employees = fields.Integer(string='Deslocated Employees', readonly=False)
    deslocation_nr = fields.Integer(string='Deslocation Number', readonly=False)
    unionized_employees_in_october = fields.Integer(string='Unionized Employees in October', readonly=False,
                                                    compute='_compute_unionized_employees')
    in_worker_association = fields.Boolean(string='In Worker Association', readonly=False)
    employer_association = fields.Many2one('unique.report.table.8', string='Employer Association', readonly=False)
    has_supplementary_work = fields.Boolean(string='Has Supplementary Work', readonly=False,
                                            compute='_compute_has_supplementary_work', store=True)
    supp_hours_descrimination = fields.Boolean(string='Supplementary Work Hours Discrimination', readonly=False)
    temporary_workers_in_october = fields.Integer(string='Temporary Workers in October',
                                                  readonly=False)  # ver como calcular
    temporary_workers_in_december = fields.Integer(string='Temporary Workers in December',
                                                   readonly=False)  # ver como calcular
    temporary_workers_avg = fields.Integer(string='Temporary Workers Average', readonly=False)  # ver como calcular
    temporary_worker_entries_male = fields.Integer(string='Temporary Worker Entries (Male)',
                                                   readonly=False)  # ver como calcular
    temporary_worker_entries_female = fields.Integer(string='Temporary Worker Entries (Female)',
                                                     readonly=False)  # ver como calcular
    temporary_worker_exits_male = fields.Integer(string='Temporary Worker Exits (Male)',
                                                 readonly=False)  # ver como calcular
    temporary_worker_exits_female = fields.Integer(string='Temporary Worker Exits (Female)',
                                                   readonly=False)  # ver como calcular
    # falta por grupo etário

    # Annex 0 Fields
    annex_0_employees = fields.One2many('unique.report.annex.0.employee', 'unique_report_id',
                                        string='Annex 0 Employees')

    @api.depends('company_status')
    def _compute_company_status_reason_visible(self):
        for record in self:
            record.company_status_reason_visible = record.company_status.code in ['2', '3']

    @api.depends('reference_year')
    def _compute_employees_in_service_december(self):
        for record in self:
            record.employees_in_service_december = self.env['hr.employee'].search_count([
                ('company_id', '=', record.company_id.id),
                ('contract_date_start', '!=', False),
                '|',
                ('contract_date_end', '>=', f'{record.reference_year}-12-31'),
                ('contract_date_end', '=', False)
            ])

    def _compute_employee_in_service_december_avg(self):
        for record in self:
            total_employees = 0
            year = int(record.reference_year)
            for month in range(1, 13):
                last_day = calendar.monthrange(year, month)[1]
                employees = self.env['hr.employee'].search_count([
                    ('company_id', '=', record.company_id.id),
                    ('contract_date_start', '!=', False),
                    '|',
                    ('contract_date_end', '>=', f'{year}-{month:02d}-{last_day}'),
                    ('contract_date_end', '=', False)
                ])
                total_employees += employees

            record.employee_in_service_december_avg = math.ceil(total_employees / 12)

    def _compute_unionized_employees(self):
        for record in self:
            record.unionized_employees_in_october = self.env['hr.employee'].search_count([
                ('company_id', '=', record.company_id.id),
                ('contract_date_start', '!=', False),
                ('union_worker', '=', True),
                '|',
                ('contract_date_end', '>=', f'{record.reference_year}-10-31'),
                ('contract_date_end', '=', False)
            ])

    @api.depends('reference_year')
    def _compute_has_supplementary_work(self):
        for record in self:
            count = self.env['hr.payslip.line'].search_count([
                ('company_id', '=', record.company_id.id),
                ('slip_id.state', 'in', ['done', 'paid']),
                ('slip_id.date_from', '>=', f'{record.reference_year}-01-01'),
                ('slip_id.date_to', '<=', f'{record.reference_year}-12-31'),
                ('salary_rule_id.code', '=', 'SW')
            ])
            record.has_supplementary_work = bool(count)

    def get_annex_0_employee_summary(self):
        # quadro VII do Anexo 0 (XML)
        employees = self.mapped('annex_0_employees') if hasattr(self, 'annex_0_employees') else self

        result = {
            "age_groups"     : {},
            "literacy_groups": {},
            "age_totals"     : {},
            "literacy_totals": {}
        }

        age_groups = {
            'lt18'   : lambda age: age < 18,
            '18_34'  : lambda age: 18 <= age <= 34,
            '35_44'  : lambda age: 35 <= age <= 44,
            '45_64'  : lambda age: 45 <= age <= 64,
            '65_plus': lambda age: age >= 65,
        }

        literacy_groups = {
            'basic'         : lambda code: code and code.startswith(('1', '21', '22')),
            'third_cycle'   : lambda code: code and code.startswith('23'),
            'secondary'     : lambda code: code and code.startswith('3'),
            'post_secondary': lambda code: code and code.startswith('4'),
            'higher'        : lambda code: code and code.startswith(('0', '5')),
        }

        incap_ranges = {
            'lt60' : lambda p: p < 60,
            '60_80': lambda p: 60 <= p < 80,
            'gt80' : lambda p: p >= 80
        }

        genders = ['1', '2']

        for age_key in age_groups:
            result["age_groups"][age_key] = {g: {'lt60': 0, '60_80': 0, 'gt80': 0} for g in genders}
            result["age_totals"][age_key] = {g: 0 for g in genders}

        for lit_key in literacy_groups:
            result["literacy_groups"][lit_key] = {g: {'lt60': 0, '60_80': 0, 'gt80': 0} for g in genders}
            result["literacy_totals"][lit_key] = {g: 0 for g in genders}

        for emp in employees:
            gender = emp.employee_gender or '0'
            if gender not in genders:
                continue

            perc = emp.inability_percentage * 100 or 0
            age = emp.employee_age or 0
            lit_code = emp.employee_literacy_habilitations.code if emp.employee_literacy_habilitations else ''

            # Age group
            for age_key, age_check in age_groups.items():
                if age_check(age):
                    for perc_key, perc_check in incap_ranges.items():
                        if perc_check(perc):
                            result['age_groups'][age_key][gender][perc_key] += 1
                    result['age_totals'][age_key][gender] += 1

            # Literacy group
            for lit_key, lit_check in literacy_groups.items():
                if lit_check(lit_code):
                    for perc_key, perc_check in incap_ranges.items():
                        if perc_check(perc):
                            result['literacy_groups'][lit_key][gender][perc_key] += 1
                    result['literacy_totals'][lit_key][gender] += 1

        return result

    business_volume = fields.Float(string='Business Volume')
    business_volume_year = fields.Integer(string='Business Volume Year', default=lambda self: self.reference_year)
    social_capital = fields.Float(string='Social Capital', readonly=False)
    social_capital_rep_private_national = fields.Float(string='Social Capital Rep Private National', readonly=False)
    social_capital_rep_foreign = fields.Float(string='Social Capital Rep Foreign', readonly=False)
    social_capital_rep_public_national = fields.Float(string='Social Capital Rep Public National', readonly=False)

    company_funded_amount = fields.Float(string='Funded Company Amount', readonly=False)
    company_funded_amount_hours = fields.Float(string='Funded Company Hours', readonly=False)
    company_funded_amount_remaining = fields.Float(string='Funded Company Remaining', readonly=False)
    external_funded_amount = fields.Float(string='Funded External Amount', readonly=False)
    external_funded_amount_esf = fields.Float(string='Funded External ESF', readonly=False)
    external_funded_amount_other = fields.Float(string='Funded External Other', readonly=False)

    total_training_charges = fields.Float(string='TOTAL', readonly=False)

    @api.onchange('company_funded_amount_hours', 'company_funded_amount_remaining')
    def _compute_company_funded_amount(self):
        self.company_funded_amount = self.company_funded_amount_hours + self.company_funded_amount_remaining

    @api.onchange('external_funded_amount_esf', 'external_funded_amount_other')
    def _compute_external_funded_amount(self):
        self.external_funded_amount = self.external_funded_amount_esf + self.external_funded_amount_other

    @api.onchange('company_funded_amount', 'external_funded_amount')
    def _compute_total_training_charges(self):
        self.total_training_charges = self.company_funded_amount + self.external_funded_amount

    safety_health_management_charges = fields.Float(string='Safety Health Organization Charges', readonly=False)
    workspace_management_charges = fields.Float(string='Workspace Management Charges', readonly=False)
    goods_services_aquisition_charges = fields.Float(string='Goods Services Acquisition Charges', readonly=False)
    consulting_info_training_charges = fields.Float(string='Consulting Info Training Charges', readonly=False)
    other_charges = fields.Float(string='Other Charges', readonly=False)
    total_charges = fields.Float(string='Total Charges', readonly=False)

    @api.onchange(
        'safety_health_management_charges',
        'workspace_management_charges',
        'goods_services_aquisition_charges',
        'consulting_info_training_charges',
        'other_charges')
    def _compute_total_charges(self):
        self.total_charges = self.safety_health_management_charges + self.workspace_management_charges + \
                             self.goods_services_aquisition_charges + self.consulting_info_training_charges + \
                             self.other_charges

    had_ten_employees_in_october = fields.Boolean(string='Had 10 Employees in October', readonly=False,
                                                  compute='_compute_had_ten_employees_in_october')
    gross_added_value = fields.Float(string='Gross Added Value', readonly=False)
    gross_added_value_year = fields.Integer(string='Gross Added Value Year', readonly=False,
                                            default=lambda self: self.reference_year)
    personnel_cost = fields.Float(string='Personnel Cost', readonly=False)
    year_amortization = fields.Float(string='Year Amortization', readonly=False)
    year_provision = fields.Float(string='Year Provision', readonly=False)
    financial_costs_and_losses = fields.Float(string='Financial Costs and Losses', readonly=False)
    income_tax = fields.Float(string='Income Tax', readonly=False)
    net_income = fields.Float(string='Net Income', readonly=False)

    sick_allowance = fields.Float(string='Sick Allowance', readonly=False)
    sick_allowance_code = fields.Many2one('unique.report.table.9', string='Sick Allowance Code', readonly=False)
    age_allowance = fields.Float(string='Age Allowance', readonly=False)
    age_allowance_code = fields.Many2one('unique.report.table.9', string='Age Allowance Code', readonly=False)
    other_ss_charges = fields.Float(string='Other Social Security Charges', readonly=False)
    other_ss_charges_code = fields.Many2one('unique.report.table.9', string='Other Social Security Charges Code',
                                            readonly=False)

    not_supported_sick_allowance = fields.Float(string='Not Supported Sick Allowance', readonly=False)
    not_supported_sick_allowance_code = fields.Many2one('unique.report.table.9',
                                                        string='Not Supported Sick Allowance Code', readonly=False)
    not_supported_age_allowance = fields.Float(string='Not Supported Age Allowance', readonly=False)
    not_supported_age_allowance_code = fields.Many2one('unique.report.table.9',
                                                       string='Not Supported Age Allowance Code', readonly=False)
    not_supported_other_ss_charges = fields.Float(string='Not Supported Other Social Security Charges', readonly=False)
    not_supported_other_ss_charges_code = fields.Many2one('unique.report.table.9',
                                                          string='Not Supported Other Social Security Charges Code',
                                                          readonly=False)

    social_support_charges = fields.Float(string='Social Support Charges', readonly=False)

    max_annual_potential = fields.Float(string='Max Annual Potential', readonly=False)

    not_worked_hours_table = fields.One2many('unique.report.not.worked.hours', 'unique_report_id',
                                             string='Not Worked Hours')

    def _compute_had_ten_employees_in_october(self):
        for report in self:
            report.had_ten_employees_in_october = report.employees_in_service_october >= 10

    #     Annex A fields

    company_name = fields.Char(string='Company Name', related='company_id.name', readonly=True)
    company_address = fields.Char(string='Company Address', related='company_id.street', readonly=True)
    company_city = fields.Char(string='City', related='company_id.city', readonly=True)
    company_postal_code = fields.Char(string='Company Postal Code', related='company_id.zip', readonly=True)
    company_country = fields.Many2one('res.country', string='Company Country', related='company_id.country_id',
                                      readonly=True)
    company_country_code = fields.Char(related='company_id.country_code', readonly=True)
    company_municipality = fields.Many2one('unique.report.table.3', string='Company Locale',
                                           related='company_id.municipality', readonly=False)
    company_email = fields.Char(string='Company Email', related='company_id.email', readonly=True)
    company_phone = fields.Char(string='Company Phone', related='company_id.phone', readonly=True)
    main_activity_cae = fields.Many2one('unique.report.table.4', string='Main Activity CAE',
                                        related='company_id.main_activity_cae', readonly=False)
    legal_nature = fields.Many2one('unique.report.table.7', string='Legal Nature', related='company_id.legal_nature',
                                   readonly=False)
    employees_in_service = fields.Integer(string='Employees in Service', compute='_compute_employees_in_service',
                                          store=True, readonly=False)
    employees_in_service_october = fields.Integer(string='Employees in Service on 31st October',
                                                  compute='_compute_employees_in_service_october', store=True,
                                                  readonly=False)

    annex_a_employees = fields.One2many('unique.report.annex.a.employee', 'unique_report_id',
                                        string='Annex A Employees')

    #     Annex B fields

    entries_exits_ref_year = fields.Boolean(string='Entries and Exits in the Reference Year', default=False)
    annex_b_employees = fields.One2many('unique.report.annex.b.employee', 'unique_report_id',
                                        string='Annex B Employees')

    @api.depends('reference_year')
    def _compute_employees_in_service(self):
        for record in self:
            record.employees_in_service = self.env['hr.employee'].search_count(
                [('company_id', '=', record.company_id.id),
                 ('contract_date_start', '!=', False),
                 '|', ('contract_date_end', '=', False),
                 ('contract_date_end', '>=', fields.Date.context_today(record))])

    @api.depends('reference_year')
    def _compute_employees_in_service_october(self):
        for record in self:
            record.employees_in_service_october = self.env['hr.employee'].search_count(
                [('company_id', '=', record.company_id.id),
                 ('contract_date_start', '<=', f'{int(record.reference_year)}-10-31'),
                 '|', ('contract_date_end', '=', False),
                 ('contract_date_end', '>=', f'{int(record.reference_year)}-10-31')])

    def _populate_annex_a_employees(self):
        self.annex_a_employees = [(5, 0, 0)]  # Clear existing records
        employees = self.env['hr.employee'].search(
            [('company_id', '=', self.company_id.id),
             ('contract_date_start', '<=', f'{int(self.reference_year)}-10-31'),
             '|', ('contract_date_end', '=', False),
             ('contract_date_end', '>=', f'{int(self.reference_year)}-10-31')])
        employee_lines = []
        for employee in employees:
            employee_lines.append((0, 0, {
                'employee_id': employee.id,
            }))
        self.annex_a_employees = employee_lines
        self.annex_a_employees._compute_employee_gender()
        self.annex_a_employees._compute_employee_weekly_hours()
        self.annex_a_employees._compute_employee_base_salary_october()
        self.annex_a_employees._compute_employee_paid_hours_october()
        self.annex_a_employees._compute_employee_meal_allw_october()
        self.annex_a_employees._compute_employee_other_regular_allw_october()
        self.annex_a_employees._compute_employee_other_irregular_allw_october()
        self.annex_a_employees._compute_employee_supplementary_work_amount_october()

    def _populate_annex_b_employees(self):
        self.annex_b_employees = [(5, 0, 0)]
        exiting_employees = self.env['hr.employee'].search(
            [('company_id', '=', self.company_id.id),
             ('contract_date_end', '>=', f'{self.reference_year}-01-01'),
             ('contract_date_end', '<=', f'{self.reference_year}-12-31')])
        # v19: first_contract_date deixou de ser campo, logo nao e pesquisavel.
        # Filtra-se em Python com _get_first_contract_date().
        year_start = fields.Date.to_date(f'{self.reference_year}-01-01')
        year_end = fields.Date.to_date(f'{self.reference_year}-12-31')
        entering_employees = self.env['hr.employee'].search(
            [('company_id', '=', self.company_id.id),
             ('contract_date_start', '!=', False)]).filtered(
            lambda e: (d := e._get_first_contract_date()) and year_start <= d <= year_end)

        employee_lines = []
        added_employee_ids = set()

        for employee in exiting_employees:
            if employee.id not in added_employee_ids:
                employee_lines.append((0, 0, {
                    'employee_id': employee.id,
                }))
                added_employee_ids.add(employee.id)

        for employee in entering_employees:
            if employee.id not in added_employee_ids:
                employee_lines.append((0, 0, {
                    'employee_id': employee.id,
                }))
                added_employee_ids.add(employee.id)

        self.annex_b_employees = employee_lines
        self.annex_b_employees._compute_employee_gender()
        self.annex_b_employees._compute_employee_weekly_hours()
        self.annex_b_employees._compute_employee_base_salary_october()
        self.annex_b_employees._compute_employee_paid_hours_october()
        self.annex_b_employees._compute_employee_meal_allw_october()
        self.annex_b_employees._compute_employee_other_regular_allw_october()
        self.annex_b_employees._compute_employee_other_irregular_allw_october()
        self.annex_b_employees._compute_employee_supplementary_work_amount_october()
        self.annex_b_employees._compute_employee_exit_date()

    #     Annex C fields

    had_employees_in_service = fields.Boolean(string='Had Employees in Service', default=True)
    annex_c_employee_training = fields.One2many('unique.report.annex.c.employee.training', 'unique_report_id',
                                                string='Annex C Employee Training')

    def _populate_annex_c_employee_training(self):
        self.annex_c_employee_training = [(5, 0, 0)]

        training_types = self.env['hr.leave.type'].search([('is_training', '=', True)])
        if not training_types:
            return

        lines = []

        for training_type in training_types:
            leaves = self.env['hr.leave'].search([
                ('holiday_status_id', '=', training_type.id),
                ('state', '=', 'validate'),
                ('employee_id.company_id', '=', self.company_id.id),
                ('employee_id.contract_date_start', '!=', False),
                ('date_from', '>=', f'{self.reference_year}-01-01'),
                ('date_to', '<=', f'{self.reference_year}-12-31'),
            ])

            sorted_leaves = sorted(leaves, key=lambda l: (l.employee_id.id, l.date_from))

            for leave in sorted_leaves:
                lines.append((0, 0, {
                    'employee_id'                          : leave.employee_id.id,
                    'employee_ss_regimen'                  : leave.employee_id.social_security_regimen.id,
                    'employee_training_frequency'          : leave.training_frequency.id if hasattr(leave,
                                                                                                    'training_frequency') else False,
                    'employee_training_ref_period'         : leave.training_ref_period.id if hasattr(leave,
                                                                                                     'training_ref_period') else False,
                    'employee_training_area'               : leave.training_area.id if hasattr(leave,
                                                                                               'training_area') else False,
                    'employee_training_type'               : leave.training_type.id if hasattr(leave,
                                                                                               'training_type') else False,
                    'employee_training_initiative'         : leave.training_initiative.id if hasattr(leave,
                                                                                                     'training_initiative') else False,
                    'employee_training_schedule'           : leave.training_schedule.id if hasattr(leave,
                                                                                                   'training_schedule') else False,
                    'employee_training_entity'             : leave.training_entity.id if hasattr(leave,
                                                                                                 'training_entity') else False,
                    'employee_training_certificate_type'   : leave.training_certificate_type.id if hasattr(leave,
                                                                                                           'training_certificate_type') else False,
                    'employee_training_qualification_level': leave.training_qualification_level.id if hasattr(leave,
                                                                                                              'training_qualification_level') else False,
                    'employee_training_duration'           : leave.number_of_hours if hasattr(leave,
                                                                                              'number_of_hours') else False,
                }))

        self.annex_c_employee_training = lines

    # Annex E fields

    had_strikes = fields.Boolean(string='Had Strikes', default=False)
    annex_e_strike_line_ids = fields.One2many('unique.report.strike', 'unique_report_id', string='Strikes')

    def _populate_annex_e_strike_lines(self):
        self.ensure_one()
        self.annex_e_strike_line_ids = [(5, 0, 0)]

        strike_types = self.env['hr.leave.type'].search([('is_strike', '=', True)])
        if not strike_types:
            return

        for strike_type in strike_types:
            leaves = self.env['hr.leave'].search([
                ('holiday_status_id', '=', strike_type.id),
                ('state', '=', 'validate'),
                ('employee_id.company_id', '=', self.company_id.id),
                ('date_from', '>=', f'{self.reference_year}-01-01'),
                ('date_to', '<=', f'{self.reference_year}-12-31'),
            ])

        # Agrupar por data, código, claim e result
        grouped = defaultdict(list)
        for leave in leaves:
            key = (
                leave.date_from.date() if leave.date_from else None,
                leave.strike_code,
                leave.strike_claim.id if leave.strike_claim else None,
                leave.strike_result.id if leave.strike_result else None
            )
            grouped[key].append(leave)

        lines = []
        for (strike_date, code, claim_id, result_id), group_leaves in grouped.items():
            duration = group_leaves[0].number_of_hours or 0.0
            total_employees = len(group_leaves)

            duration_hours = int(duration)
            duration_minutes = int((duration - duration_hours) * 60)

            lines.append((0, 0, {
                'strike_code'            : code,
                'strike_claim'           : claim_id,
                'strike_result'          : result_id,
                'strike_date'            : strike_date,
                'strike_working_hours'   : self.company_id.resource_calendar_id.hours_per_week,
                'strike_employee_count'  : total_employees,
                'strike_duration_hours'  : duration_hours,
                'strike_duration_minutes': duration_minutes,
            }))

        self.annex_e_strike_line_ids = lines
        self.annex_e_strike_line_ids._compute_strike_working_hours()

    def action_populate_annex_a_employees(self):
        self.ensure_one()
        self._populate_annex_a_employees()

    def action_populate_annex_b_employees(self):
        self.ensure_one()
        self._populate_annex_b_employees()

    def action_populate_annex_c_employee_training(self):
        self.ensure_one()
        self._populate_annex_c_employee_training()

    def action_populate_annex_e_strike_lines(self):
        self.ensure_one()
        self._populate_annex_e_strike_lines()

    @api.onchange('reference_year')
    def _onchange_reference_year(self):
        self._populate_annex_a_employees()
        self._populate_annex_b_employees()
        self._populate_annex_c_employee_training()
        self._populate_annex_e_strike_lines()

    def action_export_annex_0(self):
        self.ensure_one()
        return self.with_context(export_annex='annex_0').action_open_export_wizard()

    def action_export_annex_a(self):
        self.ensure_one()
        return self.with_context(export_annex='annex_a').action_open_export_wizard()

    def action_export_annex_b(self):
        self.ensure_one()
        return self.with_context(export_annex='annex_b').action_open_export_wizard()

    def action_export_annex_c(self):
        self.ensure_one()
        return self.with_context(export_annex='annex_c').action_open_export_wizard()

    def action_export_annex_e(self):
        self.ensure_one()
        return self.with_context(export_annex='annex_e').action_open_export_wizard()

    def action_open_export_wizard(self):
        self.ensure_one()

        wizard = self.env['unique.report.export.wizard'].create({
            'unique_report_id': self.id,
        })

        wizard.export_xml()

        return {
            'type'     : 'ir.actions.act_window',
            'res_model': 'unique.report.export.wizard',
            'view_mode': 'form',
            'res_id'   : wizard.id,
            'target'   : 'new',
        }


class UniqueReportAnnexAEmployee(models.Model):
    _name = 'unique.report.annex.a.employee'
    _description = 'Unique Report Annex A Employee'

    unique_report_id = fields.Many2one('unique.report', string='Unique Report', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    company_local_unit_number = fields.Char(string='Local Unit Number',
                                            related='unique_report_id.local_unit_number', readonly=True)
    employee_social_security_regimen = fields.Many2one('unique.report.table.11',
                                                       string='Social Security Regimen',
                                                       related='employee_id.social_security_regimen', readonly=False)
    employee_niss = fields.Char(string='NISS', related='employee_id.ssnid', readonly=True)
    employee_gender = fields.Char(compute='_compute_employee_gender', readonly=False, string="Gender")
    employee_birthdate = fields.Date(string='Birthdate', related='employee_id.birthday', readonly=False)
    # v19: hr.employee.first_contract_date deixou de ser campo e passou a ser o
    # metodo _get_first_contract_date() (hr/models/hr_employee.py:494), por isso
    # ja nao serve para related nem para domains.
    employee_admission_date = fields.Date(string='Admission Date',
                                          compute='_compute_employee_admission_date',
                                          store=True, readonly=True)
    employee_last_promotion_date = fields.Date(string='Last Promotion',
                                               related='employee_id.last_promotion_date', readonly=False)
    employee_contract_type = fields.Many2one('unique.report.table.13', string='Contract Type',
                                             related='employee_id.version_id.contract_type', readonly=False)
    employee_nationality = fields.Char(string='Nationality', related='employee_id.country_id.code',
                                       readonly=False)
    employee_literacy_habilitations = fields.Many2one('unique.report.table.14', string='Literacy Habilitations',
                                                      related='employee_id.literacy_habilitations', readonly=False)
    employee_job_situation = fields.Many2one('unique.report.table.15', string='Job Situation',
                                             related='employee_id.job_situation', readonly=False)
    employee_job_ur = fields.Many2one('unique.report.table.16', string='Job', related='employee_id.job_ur',
                                      readonly=False)
    employee_irct_regulation = fields.Char(string='IRCT Regulation', related='employee_id.irct_regulation',
                                           readonly=False)
    employee_irct_applicability = fields.Many2one('unique.report.table.19', string='IRCT Applicability',
                                                  related='employee_id.irct_applicability', readonly=False)
    employee_job_category = fields.Char(string='Professional Category', related='employee_id.job_category',
                                        readonly=False)
    employee_qualification_level = fields.Many2one('unique.report.table.21', string='Qualification Level',
                                                   related='employee_id.qualification_level', readonly=False)
    employee_work_duration_regimen = fields.Many2one('unique.report.table.22', string='Work Duration Regimen',
                                                     related='employee_id.work_duration_regimen', readonly=False)
    employee_weekly_hours = fields.Float(string='Weekly Hours', readonly=False,
                                         compute='_compute_employee_weekly_hours', )
    employee_working_time_duration = fields.Many2one('unique.report.table.23', string='Work Duration',
                                                     related='employee_id.working_time_duration', readonly=False)
    employee_working_time_organization = fields.Many2one('unique.report.table.24', string='Work Organization',
                                                         related='employee_id.working_time_organization',
                                                         readonly=False)
    employee_base_salary_october = fields.Float(string='Base Salary on 31st October',
                                                compute='_compute_employee_base_salary_october', store=True,
                                                readonly=False)
    employee_base_salary_paid_october = fields.Float(string='Base Salary Paid on 31st October', readonly=False)
    employee_not_paid_reason = fields.Many2one('unique.report.table.25', string='Not Paid Reason',
                                               readonly=False)
    employee_paid_hours_october = fields.Float(string='Paid Hours on 31st October',
                                               compute='_compute_employee_paid_hours_october', store=True,
                                               readonly=False)
    employee_meal_allw_october = fields.Float(string='Meal Allowance on 31st October',
                                              compute='_compute_employee_meal_allw_october', store=True, readonly=False)
    employee_shift_allw_october = fields.Float(string='Shift Allowance on 31st October', readonly=False)
    employee_other_regular_allw_october = fields.Float(string='Other Regular Allowance',
                                                       compute='_compute_employee_other_regular_allw_october',
                                                       store=True, readonly=False)  # ss_code == B
    employee_other_irregular_allw_october = fields.Float(string='Other Irregular Allowance',
                                                         compute='_compute_employee_other_irregular_allw_october',
                                                         store=True, readonly=False)  # ss_code == O, N, F
    employee_supplementary_work_amount_october = fields.Float(string='supplementary Work Amount',
                                                              compute='_compute_employee_supplementary_work_amount_october',
                                                              store=True, readonly=False)  # regra TS
    employee_supplementary_work_hours_october = fields.Float(string='supplementary Work Hours', readonly=False)
    employee_supplementary_work_civil_year = fields.Float(string='supplementary Work Civil Year')
    employee_supplementary_work_civil_year_hours = fields.Float(string='supplementary Work Civil Year Hours')
    employee_supplementary_work_civil_year_hours_n_2 = fields.Float(string='supplementary Work Civil Year Hours N.2',
                                                                    readonly=False)

    @api.depends('employee_id', 'employee_id.sex')
    def _compute_employee_gender(self):
        for line in self:
            line.employee_gender = '1' if line.employee_id.sex == 'male' else '2' if line.employee_id.sex == 'female' else False

    @api.depends('employee_id', 'employee_id.version_ids.contract_date_start')
    def _compute_employee_admission_date(self):
        for line in self:
            line.employee_admission_date = line.employee_id._get_first_contract_date() \
                if line.employee_id else False

    def _get_october_payslips(self):
        for line in self:
            payslips = self.env['hr.payslip'].search([('employee_id', '=', line.employee_id.id), (
                'date_from', '<=', f'{int(line.unique_report_id.reference_year)}-10-31'),
                                                      (
                                                          'date_to', '>=',
                                                          f'{int(line.unique_report_id.reference_year)}-10-31'),
                                                      ('state', 'in', ['done', 'paid'])])
            if payslips:
                return payslips
            return False

    @api.depends('employee_id', 'unique_report_id.reference_year')
    def _compute_employee_base_salary_october(self):
        for line in self:
            payslips = line._get_october_payslips()
            if payslips:
                line.employee_base_salary_october = sum(payslips.line_ids.filtered(
                    lambda l: l.category_id.code == 'BASIC').mapped('total'))
                line.employee_base_salary_paid_october = line.employee_base_salary_october
            else:
                line.employee_base_salary_october = 0

    @api.depends('employee_id', 'employee_id.resource_calendar_id', 'employee_id.resource_calendar_id.hours_per_week')
    def _compute_employee_weekly_hours(self):
        for line in self:
            if line.employee_id.resource_calendar_id:
                line.employee_weekly_hours = line.employee_id.resource_calendar_id.hours_per_week
            else:
                line.employee_weekly_hours = 40

    def _format_employee_weekly_hours(self):
        for line in self:
            if line.employee_id.resource_calendar_id:
                return str(int(line.employee_weekly_hours * 10)).zfill(3)

    @api.depends('employee_id', 'unique_report_id.reference_year')
    def _compute_employee_paid_hours_october(self):
        for line in self:
            payslips = line._get_october_payslips()
            if payslips:
                line.employee_paid_hours_october = sum(payslips.worked_days_line_ids.filtered(
                    lambda l: l.code == 'WORK100').mapped('number_of_hours'))
            else:
                line.employee_paid_hours_october = 0

    @api.depends('employee_id', 'unique_report_id.reference_year')
    def _compute_employee_meal_allw_october(self):
        for line in self:
            payslips = line._get_october_payslips()
            if payslips:
                line.employee_meal_allw_october = sum(payslips.line_ids.filtered(
                    lambda l: l.category_id.code == 'SA').mapped('total'))
            else:
                line.employee_meal_allw_october = 0

    @api.depends('employee_id', 'unique_report_id.reference_year')
    def _compute_employee_other_regular_allw_october(self):
        for line in self:
            payslips = line._get_october_payslips()
            if payslips:
                line.employee_other_regular_allw_october = sum(payslips.line_ids.filtered(
                    lambda l: l.salary_rule_id.ss_code == 'B').mapped('total'))
            else:
                line.employee_other_regular_allw_october = 0

    @api.depends('employee_id', 'unique_report_id.reference_year')
    def _compute_employee_other_irregular_allw_october(self):
        for line in self:
            payslips = line._get_october_payslips()
            if payslips:
                line.employee_other_irregular_allw_october = sum(payslips.line_ids.filtered(
                    lambda l: l.salary_rule_id.ss_code in ['O', 'N', 'F']).mapped('total'))
            else:
                line.employee_other_irregular_allw_october = 0

    @api.depends('employee_id', 'unique_report_id.reference_year')
    def _compute_employee_supplementary_work_amount_october(self):
        for line in self:
            payslips = line._get_october_payslips()
            if payslips:
                line.employee_supplementary_work_amount_october = sum(payslips.line_ids.filtered(
                    lambda l: l.salary_rule_id.code == 'SW').mapped('total'))
            else:
                line.employee_supplementary_work_amount_october = 0


class UniqueReportAnnexBEmployee(models.Model):
    _name = 'unique.report.annex.b.employee'
    _inherit = 'unique.report.annex.a.employee'
    _description = 'Unique Report Annex B Employee'

    employee_entry_reason = fields.Many2one('unique.report.table.26', string='Entry Reason', readonly=False,
                                            related='employee_id.version_id.entry_reason')
    employee_exit_date = fields.Date(string='Exit Date', compute='_compute_employee_exit_date', readonly=False)
    employee_exit_reason = fields.Many2one('unique.report.table.27', string='Exit Reason', readonly=False,
                                           related='employee_id.version_id.exit_reason')
    employee_supplementary_work_civil_year_hours_n_2 = fields.Float(string='supplementary Work Civil Year Hours N.2',
                                                                    readonly=False)

    @api.depends('employee_id', 'employee_id.version_ids', 'employee_id.version_ids.contract_date_end')
    def _compute_employee_exit_date(self):
        for line in self:
            # v19: contract_ids[-1] -> ultima versao com data de fim definida.
            # Um contrato sem fim (date_end False) significa que nao houve saida.
            versions = line.employee_id.version_ids.filtered(lambda v: v.contract_date_start)
            if versions and not versions.sorted('date_version')[-1].contract_date_end:
                line.employee_exit_date = False
                continue
            dates = [v.date_end for v in versions if v.date_end]
            line.employee_exit_date = max(dates) if dates else False


class UniqueReportAnnex0Employee(models.Model):
    _name = 'unique.report.annex.0.employee'
    _description = 'Unique Report Annex 0 Employee'

    unique_report_id = fields.Many2one('unique.report', string='Unique Report', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee')

    employee_age = fields.Integer(
        string='Employee Age',
        readonly=False
    )

    employee_gender = fields.Char(
        string='Employee Gender',
        readonly=False
    )

    employee_literacy_habilitations = fields.Many2one(
        'unique.report.table.14',
        string='Literacy Habilitations',
        related='employee_id.literacy_habilitations',
        store=True,
        readonly=False
    )

    inability_percentage = fields.Float(string='Inability Percentage', readonly=False)

    @api.onchange('employee_id')
    def _compute_employee_age(self):
        for line in self:
            if line.employee_id.birthday:
                today = fields.Date.today()
                born = line.employee_id.birthday
                line.employee_age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            else:
                line.employee_age = 0

    @api.onchange('employee_id')
    def _compute_employee_gender(self):
        for line in self:
            line.employee_gender = '1' if line.employee_id.sex == 'male' else '2' if line.employee_id.sex == 'female' else False


class UniqueReportAnnexCEmployeeTraining(models.Model):
    _name = 'unique.report.annex.c.employee.training'
    _description = 'Unique Report Annex C Employee Training Lines'

    unique_report_id = fields.Many2one('unique.report', string='Unique Report', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    employee_ss_regimen = fields.Many2one('unique.report.table.11', string='Social Security Regimen')
    employee_niss = fields.Char(string='Employee NISS', related='employee_id.ssnid', readonly=False)
    employee_training_frequency = fields.Many2one('unique.report.table.28', string='Employee Training Frequency',
                                                  readonly=False)
    employee_training_ref_period = fields.Many2one('unique.report.table.29', string='Employee Training Ref Period',
                                                   readonly=False)
    employee_training_area = fields.Many2one('unique.report.table.30', string='Employee Training Area', readonly=False)
    employee_training_type = fields.Many2one('unique.report.table.31', string='Employee Training Type', readonly=False)
    employee_training_initiative = fields.Many2one('unique.report.table.32', string='Employee Training Initiative',
                                                   readonly=False)
    employee_training_schedule = fields.Many2one('unique.report.table.33', string='Employee Training Schedule',
                                                 readonly=False)
    employee_training_entity = fields.Many2one('unique.report.table.34', string='Employee Training Entity',
                                               readonly=False)
    employee_training_certificate_type = fields.Many2one('unique.report.table.35',
                                                         string='Employee Training Certificate Type', readonly=False)
    employee_training_qualification_level = fields.Many2one('unique.report.table.36',
                                                            string='Employee Training Qualification Level',
                                                            readonly=False)
    employee_training_duration = fields.Float(string='Training Duration', readonly=False)


class UniqueReportNotWorkedHours(models.Model):
    _name = 'unique.report.not.worked.hours'
    _description = 'Unique Report Not Worked Hours'

    unique_report_id = fields.Many2one('unique.report', string='Unique Report', ondelete='cascade')
    not_worked_hours_reason = fields.Many2one('unique.report.table.10', string='Not Worked Hours Reason',
                                              readonly=False)
    paid_leave_hours_male = fields.Float(string='Paid Leave Hours (M)', readonly=False)
    paid_leave_hours_female = fields.Float(string='Paid Leave Hours (F)', readonly=False)
    unpaid_leave_hours_male = fields.Float(string='Unpaid Leave Hours (M)', readonly=False)
    unpaid_leave_hours_female = fields.Float(string='Unpaid Leave Hours (F)', readonly=False)


class UniqueReportStrike(models.Model):
    _name = 'unique.report.strike'
    _description = 'Unique Report Not Worked Hours'

    unique_report_id = fields.Many2one('unique.report', string='Unique Report', ondelete='cascade')
    strike_code = fields.Char(string='Strike Code', readonly=False)
    strike_claim = fields.Many2one('unique.report.table.52', string='Strike Claim', readonly=False)
    strike_result = fields.Many2one('unique.report.table.53', string='Strike Result', readonly=False)
    strike_date = fields.Date(string='Strike Date', readonly=False)
    strike_working_hours = fields.Float(
        string='Strike Working Hours',
        compute='_compute_strike_working_hours',
        store=True,
        readonly=False
    )
    strike_employee_count = fields.Integer(string='Strike Employee Count', readonly=False)
    strike_duration_hours = fields.Integer(string='Strike Duration (Hours)', readonly=False)
    strike_duration_minutes = fields.Integer(string='Strike Duration (Minutes)', readonly=False)

    @api.depends('unique_report_id.company_id')
    def _compute_strike_working_hours(self):
        for line in self:
            calendar = line.unique_report_id.company_id.resource_calendar_id
            line.strike_working_hours = calendar.hours_per_week if calendar else 40.0
