import base64
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html2plaintext, is_html_empty, format_date, float_round, date_utils

import calendar

_logger = logging.getLogger(__name__)
ENTRIES_TO_DISCOUNT = ['PATERNITY_LEAVE', 'PARENTAL_LEAVE', 'MATERNITY_LEAVE', 'UNJUSTIFIED_ABSENCE', 'LEAVE110',
                       'HOLIDAY']


class Payslip(models.Model):
    _inherit = ['hr.payslip', 'mail.thread']
    _name = 'hr.payslip'

    income_locale = fields.Selection([
        ('C', 'Continent'),
        ('RA', 'Autonomous Region of Azores'),
        ('RM', 'Autonomous Region of Madeira'),
        ('E', 'Foreign Country'),
    ], compute='_get_income_locale', tracking=True, readonly=False)

    def _get_entries_to_discount_codes(self):
        """
        Returns list of work entry type codes that should discount/subtract
        from salary (absences, unpaid leaves, etc.)

        This is used in salary rule calculations to apply negative sign
        to corrections for these entry types.
        """
        return entries_to_discount_wage(self)

    @api.depends('employee_id', 'worked_days_line_ids', 'date_from', 'date_to')
    def _get_meal_allw_days(self):
        for slip in self:
            line = slip.worked_days_line_ids.filtered(
                lambda l: not l.is_correction and l.work_entry_type_id.code == 'WORK100')
            if slip.company_id.food_allw_payment_type == 'fixed_days':
                slip.meal_allw_days = slip.company_id.food_allw_max_days if int(
                    slip.company_id.food_allw_discount_month) != slip.date_from.month else 0
            elif slip.company_id.food_allw_payment_type == 'fixed_days_discounting':
                slip.meal_allw_days = slip.company_id.food_allw_max_days - sum(slip.worked_days_line_ids.filtered(
                    lambda l: not l.is_correction and l.work_entry_type_id.discounts_salary).mapped(
                    'number_of_days')) if int(slip.company_id.food_allw_discount_month) != slip.date_from.month else 0
            else:
                slip.meal_allw_days = line.number_of_days

    @api.depends('employee_id')
    def _get_income_locale(self):
        for rec in self:
            if rec.employee_id:
                if rec.employee_id.private_state_id == rec.env.ref('base.state_pt_pt-20'):
                    rec.income_locale = 'RA'
                elif rec.employee_id.private_state_id == rec.env.ref('base.state_pt_pt-30'):
                    rec.income_locale = 'RM'
                else:
                    rec.income_locale = 'C' if rec.employee_id.private_state_id.country_id.code == 'PT' else 'E'

    meal_allw_days = fields.Float(string="Meal Allowance Days:", store=True, tracking=True,
                                  compute='_get_meal_allw_days', readonly=False)

    payslip_type = fields.Selection([
        ('normal', 'Normal'),
        ('extraordinary', 'Extraordinary'),
        ('cease', 'Cease'),
    ],
        string="Payslip Type:",
        default='normal', tracking=True)

    vac_allw_qty = fields.Float(default=1.0, store=True, tracking=True)
    chr_allw_qty = fields.Float(default=1.0, store=True, tracking=True)
    not_used_vac_days = fields.Float(store=True, tracking=True)

    entries_date_from = fields.Date(string='Entries From', readonly=False,
                                    default=lambda self: date.today().replace(day=1))
    entries_date_to = fields.Date(string='Entries To', readonly=False,
                                  default=lambda self: datetime.now().date() + relativedelta(months=+1, day=1, days=-1))

    income_title = fields.Char(default="Vencimento Base", tracking=True)

    days_worked = fields.Float(string="Days Worked", compute='_compute_days_worked', store=True, tracking=True,
                               readonly=False)

    contract_wage = fields.Monetary(string="Contract Wage", compute='_compute_contract_wage', store=True, readonly=True,
                                    currency_field='currency_id')

    contract_schedule_exemption = fields.Monetary(string="Contract Schedule Exemption", compute='_compute_contract_wage',
                                                  store=True, readonly=True, currency_field='currency_id')

    discount_amount = fields.Monetary(string="Discount Amount", compute='_compute_discount_amount', store=True,
                                      readonly=True, currency_field='currency_id',
                                      help="Total amount of discounts applied to the payslip based on worked days, including schedule exemption")
    retroactive_count = fields.Integer(compute='_compute_retroactive_count', string='Retroactive Count')

    @api.depends('worked_days_line_ids')
    def _compute_discount_amount(self):
        for slip in self:
            total = 0.0
            for line in slip.worked_days_line_ids.filtered(lambda line: line.work_entry_type_id.discounts_salary):
                days = line.number_of_days
                total = (slip.version_id.wage / 30) * days
                if slip.version_id.exemption_schedule:
                    total += (slip.version_id.wage * slip.version_id.exemption_schedule_percentage / 30) * days
            slip.discount_amount = total

    @api.depends('version_id')
    def _compute_contract_wage(self):
        for slip in self:
            if slip.version_id:
                slip.contract_wage = slip.version_id.wage
                slip.contract_schedule_exemption = slip.version_id.exemption_schedule_percentage * slip.version_id.wage if slip.version_id.exemption_schedule else 0.0
            else:
                slip.contract_wage = 0.0
                slip.contract_schedule_exemption = 0.0

    @api.depends('input_line_ids.retroactive_id', 'input_line_ids.retroactive_line_id')
    def _compute_retroactive_count(self):
        for slip in self:
            retroactives = slip.input_line_ids.filtered(
                lambda line: line.retroactive_id or line.retroactive_line_id
            ).mapped('retroactive_id') | slip.input_line_ids.filtered(
                lambda line: line.retroactive_line_id
            ).mapped('retroactive_line_id.retroactive_id')
            slip.retroactive_count = len(retroactives)

    @api.depends('worked_days_line_ids')
    def _compute_days_worked(self):
        for slip in self:
            if slip.date_from and slip.date_to and slip.entries_date_from and slip.entries_date_to:
                first_day = slip.date_from
                last_day = slip.date_to.day if slip.date_to.day <= 30 else 30
                if slip.entries_date_from == slip.date_from and slip.entries_date_to == slip.date_to:
                    worked_days = 30
                else:
                    diff_days = abs((slip.entries_date_from.day - first_day.day) + (
                            last_day - slip.entries_date_to.day))
                    worked_days = 30 - diff_days
                days_not_considered = 0
                lines_to_discount = slip.worked_days_line_ids.filtered(
                    lambda w: w.work_entry_type_id.discounts_salary and not w.is_correction)
                for line in lines_to_discount:
                    days_not_considered += line.number_of_days
                worked_days -= days_not_considered
                slip.days_worked = worked_days if worked_days > 0 else 0

    def _compute_wage_per_hour(self):
        return float_round((self.version_id.wage * 12) / (52 * self.version_id.resource_calendar_id.hours_per_week),
                           2)

    @api.onchange('payslip_type')
    def _onchange_payslip_type(self):
        if self.payslip_type == 'cease':
            self.entries_date_to = self.version_id.date_end

    @api.onchange('employee_id')
    def _get_not_used_vac_days(self):
        holiday_leave = self.env['hr.leave.type'].search(
            [('work_entry_type_id', '=', self.env.ref('l10n_pt_hr_payroll.vacation_entry_type').id)])
        if self.employee_id:
            allocation = self.env['hr.leave.allocation'].search(
                [('employee_id', '=', self.employee_id.id), ('date_from', '<=', self.date_from),
                 ('date_to', '>=', self.date_to),
                 ('holiday_status_id', '=', holiday_leave.id)], limit=1)
            self.not_used_vac_days = allocation.max_leaves - allocation.leaves_taken

    def action_payslip_cancel(self):
        if not self.env.user.has_group('l10n_pt_hr_payroll.group_payroll_manager') and self.filtered(
                lambda slip: slip.state == 'done'):
            raise UserError(_("Cannot cancel a payslip that is done."))
        self.write({'state': 'cancel'})
        self.mapped('payslip_run_id').action_close()

    def action_confirm_slip(self):
        invalid_payslips = self.filtered(lambda p: p.version_id and (p.version_id.date_start > p.date_to or (
                p.version_id.date_end and p.version_id.date_end < p.date_from)))
        if invalid_payslips:
            raise ValidationError(_('The following employees have a contract outside of the payslip period:\n%s',
                                    '\n'.join(invalid_payslips.mapped('employee_id.name'))))
        if any(not slip.version_id.active for slip in self):
            raise ValidationError(_('You cannot validate a payslip on which the contract is cancelled'))
        if any(slip.state == 'cancel' for slip in self):
            raise ValidationError(_("You can't validate a cancelled payslip."))
        self.write({'state': 'done'})

        line_values = self._get_line_values(['NET'])

        self.filtered(lambda p: not p.credit_note and line_values['NET'][p.id]['total'] < 0).write(
            {'has_negative_net_to_report': True})
        self.mapped('payslip_run_id').action_close()
        # Validate work entries for regular payslips (exclude end of year bonus, ...)
        regular_payslips = self.filtered(lambda p: p.struct_id.type_id.default_struct_id == p.struct_id)
        work_entries = self.env['hr.work.entry']
        for regular_payslip in regular_payslips:
            work_entries |= self.env['hr.work.entry'].search([
                ('date_start', '<=', regular_payslip.date_to),
                ('date_stop', '>=', regular_payslip.date_from),
                ('employee_id', '=', regular_payslip.employee_id.id),
            ])
        if work_entries:
            work_entries.action_validate()

        if self.env.context.get('payslip_generate_pdf'):
            if self.env.context.get('payslip_generate_pdf_direct'):
                self._generate_pdf()
            else:
                self.write({'queued_for_pdf': True})
                payslip_cron = self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs', raise_if_not_found=False)
                if payslip_cron:
                    payslip_cron._trigger()

        retroactives = self.input_line_ids.filtered(lambda line: line.retroactive_id or line.retroactive_line_id).mapped(
            'retroactive_id') | self.input_line_ids.filtered(lambda line: line.retroactive_line_id).mapped(
            'retroactive_line_id.retroactive_id')
        if retroactives:
            retroactives.write({'state': 'processed'})

    def action_open_retroactive(self):
        self.ensure_one()
        retroactives = self.input_line_ids.filtered(
            lambda line: line.retroactive_id or line.retroactive_line_id
        ).mapped('retroactive_id') | self.input_line_ids.filtered(
            lambda line: line.retroactive_line_id
        ).mapped('retroactive_line_id.retroactive_id')
        if not retroactives:
            return False
        action = self.env['ir.actions.actions']._for_xml_id('l10n_pt_hr_payroll.action_hr_payroll_retroactive')
        if len(retroactives) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': retroactives.id,
                'views': [(False, 'form')],
            })
        else:
            action.update({
                'domain': [('id', 'in', retroactives.ids)],
                'views': [(False, 'list'), (False, 'form')],
            })
        return action

    # Campos que o proprio Odoo reescreve em computes internos. A v19 passou a
    # fazer payslip.write() dentro de _compute_basic_net (hr_payroll/models/
    # hr_payslip.py:447), o que fazia o guard de recibo extraordinario disparar
    # durante recomputes do sistema - inclusive ao carregar dados no arranque.
    _EXTRAORDINARY_GUARD_SKIP_FIELDS = {
        'basic_wage', 'gross_wage', 'net_wage', 'employer_cost',
        'worked_hours', 'sum_worked_hours', 'compute_date',
    }

    def write(self, vals):
        retroactive_inputs = self.env['hr.payslip.input']
        retroactive_lines = self.env['hr.payroll.retroactive.line']
        retroactive_headers = self.env['hr.payroll.retroactive']
        if 'state' in vals and vals['state'] == 'draft':
            retroactive_inputs = self.mapped('input_line_ids').filtered(
                lambda line: line.retroactive_id or line.retroactive_line_id)
            retroactive_lines = retroactive_inputs.mapped('retroactive_line_id')
            retroactive_headers = retroactive_inputs.mapped('retroactive_id') | retroactive_lines.mapped(
                'retroactive_id')
        res = super().write(vals)
        if vals.get('state') == 'draft':
            if retroactive_inputs:
                retroactive_inputs.unlink()
            if retroactive_lines:
                retroactive_lines.with_context(allow_retroactive_line_state_update=True).write({
                    'payslip_input_id': False,
                    'payslip_line_id': False,
                    'communication_state': 'to_communicate',
                })
            if retroactive_headers:
                retroactive_headers.write({
                    'state': 'draft',
                    'input_id': False,
                    'payslip_id': False,
                    'communication_state': 'to_communicate',
                })
        if set(vals) - self._EXTRAORDINARY_GUARD_SKIP_FIELDS:
            for payslip in self:
                if payslip.payslip_type == 'extraordinary' and not payslip.env['hr.payslip'].search(
                        [('employee_id', '=', payslip.employee_id.id), ('payslip_type', '=', 'normal'),
                         ('state', 'in', ['done', 'paid']), ('date_from', '>=', payslip.date_from),
                         ('date_to', '<=', payslip.date_to)]):
                    raise UserError(
                        _('The employee must have a normal payslip before creating an extraordinary payslip'))
        return res

    def action_payslip_draft(self):
        try:
            res = super().action_payslip_draft()
        except AttributeError:
            res = self.write({'state': 'draft'})
        retroactive_inputs = self.mapped('input_line_ids').filtered(
            lambda line: line.retroactive_id or line.retroactive_line_id)
        retroactive_lines = retroactive_inputs.mapped('retroactive_line_id')
        retroactive_headers = retroactive_inputs.mapped('retroactive_id') | retroactive_lines.mapped(
            'retroactive_id')
        if retroactive_inputs:
            retroactive_inputs.unlink()
        if retroactive_lines:
            retroactive_lines.with_context(allow_retroactive_line_state_update=True).write({
                'payslip_input_id': False,
                'payslip_line_id': False,
                'communication_state': 'to_communicate',
            })
        if retroactive_headers:
            retroactive_headers.write({
                'state': 'draft',
                'input_id': False,
                'payslip_id': False,
                'communication_state': 'to_communicate',
            })
        return res

    def _action_create_account_move(self):
        res = super(Payslip, self)._action_create_account_move()
        for rec in self:
            for line in rec.line_ids.filtered(lambda l: l.salary_rule_id.used_in_entries):
                if not line.salary_rule_id.account_debit:
                    raise ValidationError(_('The Rule %s is missing debit account', line.salary_rule_id.name))
                elif not line.salary_rule_id.account_credit:
                    raise ValidationError(_('The Rule %s is missing credit account', line.salary_rule_id.name))
        return res

    def action_print_payslip(self):
        res = super().action_print_payslip()
        report_name = self.env.ref('hr_payroll.action_report_payslip')
        for payslip in self:
            # Generate the PDF for the payslip
            pdf_content, content_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report_name, payslip.id)
            new_pdf_data = base64.b64encode(pdf_content)
            # Fetch existing PDF attachments sorted by creation date
            existing_attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'hr.payslip'),
                ('res_id', '=', payslip.id),
                ('mimetype', '=', 'application/pdf')
            ], order="create_date ASC")
            # If there are no attachments, create the first one
            if not existing_attachments:
                attachment_vals = {
                    'name'     : f'Payslip_{payslip.number}.pdf',
                    'type'     : 'binary',
                    'datas'    : new_pdf_data,
                    'res_model': 'hr.payslip',
                    'res_id'   : payslip.id,
                    'mimetype' : 'application/pdf',
                }
                self.env['ir.attachment'].sudo().create(attachment_vals)
            # If there is only one attachment (first), add the new one as the most recent
            elif len(existing_attachments) == 1:
                attachment_vals = {
                    'name'     : f'Payslip_{payslip.number}(1).pdf',
                    'type'     : 'binary',
                    'datas'    : new_pdf_data,
                    'res_model': 'hr.payslip',
                    'res_id'   : payslip.id,
                    'mimetype' : 'application/pdf',
                }
                self.env['ir.attachment'].sudo().create(attachment_vals)
            # If there are already two attachments, keep the first and replace the last
            else:
                # Unlink the last (most recent) attachment if different
                if existing_attachments[-1].datas != new_pdf_data:
                    existing_attachments[-1].sudo().unlink()
                    # Create the new attachment as the latest
                    attachment_vals = {
                        'name'     : f'Payslip_{payslip.number}(1).pdf',
                        'type'     : 'binary',
                        'datas'    : new_pdf_data,
                        'res_model': 'hr.payslip',
                        'res_id'   : payslip.id,
                        'mimetype' : 'application/pdf',
                    }
                    self.env['ir.attachment'].sudo().create(attachment_vals)
        return res

    @api.onchange('entries_date_from')
    def _check_entries_date_to(self):
        for rec in self:
            if rec.entries_date_from > rec.entries_date_to:
                rec.entries_date_to = rec.entries_date_from + relativedelta(months=+1, day=1, days=-1)

    @api.onchange('employee_id', 'version_id')
    def _check_contract_start_date(self):
        for rec in self:
            date_from = rec.date_from if rec.date_from else False
            if rec.date_from and rec.version_id.date_start and date_from < rec.version_id.date_start:
                rec.date_from = rec.version_id.date_start
            if rec.entries_date_from and rec.version_id.date_start and date_from < rec.version_id.date_start:
                rec.entries_date_from = rec.version_id.date_start

    @api.onchange('employee_id', 'version_id', 'struct_id', 'date_from', 'date_to', 'entries_date_from',
                  'entries_date_to')
    def _check_confirmed_slips(self):
        if self.env['hr.payslip'].search([('employee_id', '=', self.employee_id.id), ('date_from', '=', self.date_from),
                                          ('date_to', '=', self.date_to), ('state', 'in', ['done', 'paid'])]):
            self.warning_message = _('There is a confirmed slip for this employee in this period!')
        else:
            self.warning_message = False

    def _get_worked_day_lines_values(self, domain=None):
        self.ensure_one()
        res = []
        hours_per_day = self._get_worked_day_lines_hours_per_day()
        work_hours = self.version_id.get_work_hours(self.entries_date_from, self.entries_date_to, domain=domain)
        work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
        biggest_work = work_hours_ordered[-1][0] if work_hours_ordered else 0
        add_days_rounding = 0

        # Automatic corrections for previous periods removed from core
        # Install l10n_pt_hr_payroll_auto_corrections module to enable automatic corrections
        # Manual corrections can still be added using is_correction=True and ref_date fields

        for work_entry_type_id, hours in work_hours_ordered:
            work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
            days = round(hours / hours_per_day, 5) if hours_per_day else 0
            if work_entry_type.request_days_in_a_row == 'calendar':
                days = 0
                leave = self.env['hr.leave'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('holiday_status_id.work_entry_type_id', '=', work_entry_type.id),
                    ('state', '=', 'validate'),
                    ('request_date_from', '<=', self.date_to),
                    ('request_date_to', '>=', self.date_from)
                ])
                if leave:
                    for l in leave:
                        start_date = max(l.request_date_from, self.date_from)
                        end_date = min(l.request_date_to, self.date_to)
                        days += (end_date - start_date).days + 1
            days = 30 if days > 30 else days
            if work_entry_type_id == biggest_work:
                days += add_days_rounding
            hours = days * hours_per_day
            day_rounded = self._round_days(work_entry_type, days)
            add_days_rounding += (days - day_rounded)
            attendance_line = {
                'sequence'          : work_entry_type.sequence,
                'work_entry_type_id': work_entry_type_id,
                'number_of_days'    : day_rounded,
                'number_of_hours'   : hours,
            }
            res.append(attendance_line)
        return res

    def _get_attachment_types(self):
        res = super(Payslip, self)._get_attachment_types()
        res.update({
            'AWARD'           : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_award'),
            'ADVANCE'         : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_advance'),
            'KM'              : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_km'),
            'SALARY_DEDUCTION': self.env.ref('l10n_pt_hr_payroll.hr_rule_input_salary_deduction'),
            'AC'              : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_ac'),
            'RET_PLAN'        : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_ret_plan'),
            'CHILD_VAL'       : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_child_val'),
            'BAL_BONUS'       : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_balance_bonus'),
            'COMISSION'       : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_commissions'),
            'COMP_SUB_EDU'    : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_sub_comp_enc_education'),
            'EXP_EDU'         : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_exp_education'),
            'FAIL_ALLOW'      : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_fail_allow'),
            'EX_SCH_DED'      : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_ex_sch_ded'),
            'VAC_ALLW'        : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_vac_allw'),
            'CHR_ALLW'        : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_chr_allw'),
            'TN'              : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_night_work'),
            'HD'              : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_sunday_hours'),
            'TERM_COMP'       : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_term_comp'),
            'PERF_BONUS'      : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_perf_bonus'),
            'AC_FOREIGN'      : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_ac_foreign'),
            'KM_COMP'         : self.env.ref('l10n_pt_hr_payroll.hr_rule_input_km_comp'),

        })
        return res

    def _get_base_local_dict(self):
        res = super()._get_base_local_dict()
        res.update({
            'compute_irs_allowances'              : compute_irs_allowances,
            'compute_irs_wage'                    : compute_irs_wage,
            'entries_to_discount_wage'            : entries_to_discount_wage,
            'entries_considered_work'             : entries_considered_work,
            'calc_hours'                          : calc_hours,
            '_get_extra_hours_entries'            : _get_extra_hours_entries,
            'is_intern'                           : is_intern,
            'compute_proportionals'               : compute_proportionals,
            'taxed_value_meal_allowance'          : taxed_value_meal_allowance,
            'check_days_worked'                   : check_days_worked,
            'taxed_value_fail_allow'              : taxed_value_fail_allow,
            'get_week_days'                       : get_week_days,
            '_compute_proportionals_not_used_days': _compute_proportionals_not_used_days,
            'get_ss_rate'                         : get_ss_rate,
            'get_previous_amount'                 : get_previous_amount,
            '_get_irs_tax_cease_chr'              : _get_irs_tax_cease_chr,
            '_get_irs_tax_cease_vac'              : _get_irs_tax_cease_vac,
        })
        return res

    # methods for sending emails
    def action_payslip_send(self):
        '''
        This function opens a window to compose an email, with email template
        message loaded by default
        '''
        self.ensure_one()

        template = self.env.ref('l10n_pt_hr_payroll.mail_template_payslip')
        compose_form = self.env.ref(
            'mail.email_compose_message_wizard_form')
        self = self.with_context(
            default_model='hr.payslip',
            default_res_ids=self.ids,
            default_use_template=bool(template),
            default_template_id=template.id,
            default_composition_mode='comment',
            mark_so_as_sent=True
        )
        return {
            'type'     : 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views'    : [(compose_form.id, 'form')],
            'view_id'  : compose_form.id,
            'target'   : 'new',
            'context'  : self.env.context,
        }

    def force_payslip_send(self):
        composer_obj = self.env['mail.compose.message']
        email_act = self.action_payslip_send()
        if email_act and email_act.get('context'):
            composer_values = {}
            email_ctx = email_act['context']
            if not composer_values.get('email_from'):
                composer_values['email_from'] = self.company_id.email
            for key in ['attachment_ids']:
                if composer_values.get(key):
                    composer_values[key] = composer_values[key][0][2]
            composer_obj = composer_obj.with_context(
                mark_so_as_sent=email_ctx.get('mark_so_as_sent'),
                default_template_id=email_ctx.get('default_template_id'),
                default_composition_mode=email_ctx.get('default_composition_mode'),
                default_model=email_ctx.get('default_model'),
                default_use_template=email_ctx.get('default_use_template'),
                default_res_ids=email_ctx.get('default_res_ids')
            )
            composer = composer_obj.create(composer_values)
            composer._action_send_mail()
        return True

    # PDF Report Methods

    def _slip_name(self):
        lang = self.employee_id.lang or self.env.user.lang
        self = self.with_context(lang=lang)
        payslip_name = self.struct_id.payslip_name or _('Salary Slip')
        date = format_date(self.env, self.date_from, date_format="MMMM y", lang_code=lang)
        slip_name = '%(payslip_name)s - %(dates)s' % {
            'payslip_name': payslip_name,
            'dates'       : date
        }
        return slip_name

    def _get_fiscal_status(self):
        employee = self.employee_id
        lang = employee.lang or self.env.user.lang
        fiscal_status = _('%(depending)s holder(s), %(children)s dependent(s)') % {
            'depending': employee.with_context(lang=lang).depending,
            'children' : employee.with_context(lang=lang).children
        }
        return fiscal_status

    def allowances_section_payslip(self):
        """
        Returns lines to appear in the allowances (remunerações) section of the payslip PDF.

        Includes:
        - Regular allowances
        - Positive correction lines (additions to salary)

        Note: For extraordinary payslips, the BASIC line is excluded.
        """
        lines = self.line_ids.filtered(lambda line: line.appears_on_payslip)
        allowances = []
        correction_categories = ['BASIC_CORR', 'VAC_CORR', 'CHR_CORR', 'MEAL_CORR']

        for line in lines:
            # Exclude BASIC line for extraordinary payslips
            if self.payslip_type == 'extraordinary' and line.salary_rule_id.code == 'BASIC':
                continue

            # Exclude standard non-allowance categories
            if line.category_id.code in ['DED', 'IRS', 'NET', 'DED_SS', 'GROSS']:
                continue

            # Correction lines: only include if positive (addition to salary)
            if line.category_id.code in correction_categories:
                if line.total > 0:
                    allowances.append(line)
            else:
                # Regular allowances
                allowances.append(line)

        return allowances

    def allowances_section_payslip_report(self):
        allowances = []
        expanded_input_codes = set()
        for line in self.allowances_section_payslip():
            matching_inputs = self.input_line_ids.filtered(lambda input_line: input_line.code == line.salary_rule_id.code)
            if len(matching_inputs) > 1:
                if line.salary_rule_id.code in expanded_input_codes:
                    continue
                expanded_input_codes.add(line.salary_rule_id.code)
                for input_line in matching_inputs:
                    allowances.append({
                        'line': line,
                        'name': input_line.name or line.name,
                        'quantity': 0 if not line.salary_rule_id.show_qty_in_pdf else line.quantity,
                        'total': input_line.amount,
                    })
            else:
                allowances.append({
                    'line': line,
                    'name': matching_inputs[:1].name or line.name,
                    'quantity': line._get_line_quantity(),
                    'total': line.total,
                })
        return allowances

    def discount_section_payslip(self):
        """
        Returns lines to appear in the discounts (descontos) section of the payslip PDF.

        Includes:
        - Deductions (DED, IRS, SS)

        NOTE: Negative corrections are NOT included here - they appear in
        _get_unpaid_days() section with the reference date.
        """
        lines = self.line_ids.filtered(lambda line: line.appears_on_payslip)
        discounts = []

        for line in lines:
            is_deduction = line.category_id.code in ['DED', 'IRS', 'DED_SS']

            if is_deduction:
                # Regular deductions - always show as positive in discounts section
                line.total = abs(line.total)
                discounts.append(line)

        sorted_discounts = sorted(discounts, key=lambda line: line.category_id.code)
        return sorted_discounts

    def gross_wage_total_payslip(self):
        return self.to_receive_net() + self.discounts_total_payslip() + self.other_discounts_total()

    def to_receive_net(self):
        net = self.line_ids.filtered(lambda l: l.salary_rule_id.code == 'NET').amount
        return round(net, 2)

    def other_discounts_total(self):
        total = 0
        lines = self.line_ids.filtered(lambda line: line.salary_rule_id.code in ('RH_HABITACAO', 'RH_HABITACAO_ISENTO'))
        for line in lines:
            total += abs(line.amount)
        return total

    def discounts_total_payslip(self):
        """
        Calculate total of all discounts shown in payslip PDF.

        Includes:
        - Regular deductions (IRS, SS, etc.)

        NOTE: Negative corrections are calculated in _get_unpaid_days()
        and are not included in this total.
        """
        total = 0
        for line in self.discount_section_payslip():
            total += line.total
        return round(total, 2)

    def ref_date_payslip(self):
        return self.date_to.strftime("%Y.%m")

    def payment_to_account(self):
        total = 0
        for line in self.line_ids:
            if line.salary_rule_id.code == 'CARDREF' or line.salary_rule_id.other_benefits:
                total += line.total
        return self.to_receive_net() - total

    def meal_card_amount(self):
        line = self.line_ids.filtered(lambda l: l.salary_rule_id.code == 'CARDREF')
        return round(line.total, 2)

    def get_not_worked_days_line_notes(self, worked_days_line_ids):
        worked_days_list = self.env['hr.payslip.worked_days']
        for line in worked_days_line_ids.filtered(
                lambda l: l.payslip_id.struct_id not in l.work_entry_type_id.unpaid_structure_ids):
            if line.code != self.env.ref('hr_work_entry.work_entry_type_attendance').code:
                line.amount = 0
                worked_days_list += line
        return worked_days_list

    def _get_unpaid_days(self):
        """
        Returns list of unpaid days (absences, leaves, etc.) to display in payslip PDF.

        Includes:
        - Regular work entries that discount (absences, unpaid leaves)
        - Negative correction lines from previous periods
        """
        unpaid_days = []

        for line in self.worked_days_line_ids.filtered(lambda line: line.work_entry_type_id.discounts_salary):
            days = abs(line.number_of_days)
            total = (self.version_id.wage / 30) * days
            if self.version_id.exemption_schedule:
                total += (self.version_id.wage * self.version_id.exemption_schedule_percentage / 30) * days

            unpaid_days.append({
                'name': line.name,
                'qty': days,
                'total': -total,
                'ref_date': line.ref_date if line.is_correction else False
            })

        return unpaid_days

    def get_first_contract_start_date(self):
        for rec in self:
            # v19: contract_ids -> version_ids. As versoes sem contrato tem
            # date_start a False, por isso filtram-se antes do min().
            dates = [v.date_start for v in rec.employee_id.version_ids if v.date_start]
            if not dates:
                return ''
            return min(dates).strftime('%d-%m-%Y')

    def get_other_benefits(self):
        other_benefits = 0
        for rec in self:
            for line in rec.line_ids:
                if line.salary_rule_id.other_benefits:
                    other_benefits += line.total
        return other_benefits

    # SEPA Methods

    def _get_payments_vals(self, journal_id):
        self.ensure_one()
        res = super()._get_payments_vals(journal_id)
        res['amount'] = self.payment_to_account()
        return res

    def _get_entity_charges(self):
        line = self.line_ids.filtered(lambda l: l.salary_rule_id.code == 'EE')
        return float_round(line.total, 2)

    def _get_work_accident_value(self):
        line = self.line_ids.filtered(lambda l: l.salary_rule_id.code == 'BASIC')
        coefficient = self.employee_id.work_accident_coefficient / 100
        value = float_round(line.total, 2)
        return value * coefficient

    def _get_rule_name(self, localdict, rule, employee_lang):
        lang = super()._get_rule_name(localdict, rule, employee_lang)
        if rule.code not in ['SF', 'SN']:  # these change the name in the rule itself
            lang = rule.with_context(lang=employee_lang).name
        return lang

    def compute_sheet(self):
        # Validate employee has state filled for PT companies (required for IRS calculation)
        for slip in self:
            if slip.company_id and slip.company_id.country_id and slip.company_id.country_id.code == 'PT':
                if not slip.employee_id.private_state_id:
                    raise ValidationError(
                        _('Employee %s does not have the State field filled. '
                          'This field is required for IRS calculation.') % slip.employee_id.name
                    )

        res = super(Payslip, self).compute_sheet()
        for slip in self:
            for input_line in slip.input_line_ids.filtered(lambda line: line.retroactive_id or line.retroactive_line_id):
                salary_rule = input_line.retroactive_line_id.salary_rule_id
                if not salary_rule:
                    salary_rule = slip.line_ids.filtered(lambda line: line.salary_rule_id.code == input_line.code)[:1].salary_rule_id
                for line in slip.line_ids.filtered(lambda line: line.salary_rule_id == salary_rule):
                    line.write({
                        'retroactive_id': input_line.retroactive_id.id or input_line.retroactive_line_id.retroactive_id.id,
                        'retroactive_line_id': input_line.retroactive_line_id.id,
                        'origin_month': input_line.origin_month,
                        'payment_month': input_line.payment_month,
                        'natrem_code': input_line.natrem_code or input_line.retroactive_line_id.natrem_code,
                        'communication_state': input_line.communication_state,
                    })

        # Validate negative values only for PT structures
        # Allow negative values for:
        # 1. Deduction lines (category_id.code == 'DED')
        # 2. Correction salary rules (specific rules only)
        for slip in self:
            if slip.company_id and slip.company_id.country_id and slip.company_id.country_id.code == 'PT':
                correction_rules = [
                    self.env.ref('l10n_pt_hr_payroll.hr_payroll_rules_base_correction', raise_if_not_found=False),
                    self.env.ref('l10n_pt_hr_payroll.hr_payroll_rules_meal_allw_correction', raise_if_not_found=False),
                    self.env.ref('l10n_pt_hr_payroll.hr_payroll_rules_vac_allw_correction', raise_if_not_found=False),
                    self.env.ref('l10n_pt_hr_payroll.hr_payroll_rules_chr_allw_correction', raise_if_not_found=False),
                ]
                correction_rule_ids = [rule.id for rule in correction_rules if rule]

                invalid_negative_lines = []
                for line in slip.line_ids:
                    if line.total < 0:
                        # Check if it's allowed to be negative
                        is_deduction = line.category_id.code == 'DED'
                        is_correction = line.salary_rule_id and line.salary_rule_id.id in correction_rule_ids
                        is_retroactive_negative = bool(
                            line.salary_rule_id
                            and line.salary_rule_id.is_retroactive
                            and line.salary_rule_id.allow_negative
                        )

                        if not (is_deduction or is_correction or is_retroactive_negative):
                            invalid_negative_lines.append(line.salary_rule_id.name or line.name)

                if invalid_negative_lines:
                    raise UserError(
                        _('Payslip cannot have negative values on lines that are not deductions or corrections.\n'
                          'Invalid lines: %s') % ', '.join(invalid_negative_lines)
                    )

        return res

    # Salary Rule Compute Methods

    def _get_payslip_lines(self):

        res = super()._get_payslip_lines()

        if rule_cat_id := self.env.ref('l10n_pt_hr_payroll.hr_payroll_irs_ded', raise_if_not_found=False):
            if rule_ids :=  self.env['hr.salary.rule'].search([('category_id', '=', rule_cat_id.id)]):
                for line in res:
                    if line.get('code') in  rule_ids.mapped('code'):
                        line['ytd'] = int(line['ytd'])
        return res


def compute_proportionals(contract, payslip, line_type, base):
    paid_slips = len(payslip.env['hr.payslip'].search(
        [('employee_id', '=', payslip.employee_id.id), ('payslip_type', '=', 'normal'),
         ('state', 'in', ['done', 'paid'])]).filtered(lambda s: s.date_from.year == payslip.date_from.year))
    worked_days = payslip.days_worked
    days_proportional = (((contract.wage + base) / 12) / 30) * worked_days
    result = ((contract.wage + base) / 12) * paid_slips + days_proportional
    return result


def get_previous_amount(payslip, code):
    normal_slip = payslip.env['hr.payslip'].search(
        [('employee_id', '=', payslip.employee_id.id), ('payslip_type', '=', 'normal'),
         ('state', 'in', ['done', 'paid'])]).filtered(
        lambda s: s.date_from.month == payslip.date_from.month and s.date_from.year == payslip.date_from.year)
    # Ensure we only get one payslip (take the most recent one if multiple exist)
    normal_slip = normal_slip.sorted('id', reverse=True)[:1]
    if not normal_slip:
        return 0.0
    line = normal_slip.line_ids.filtered(lambda l: l.salary_rule_id.code == code)
    # Ensure we only get one line
    line = line[:1]
    return line.total if line else 0.0


def _compute_proportionals_not_used_days(contract, base):
    return float_round(((contract.wage + base) / 22), 2)


def is_intern(contract):
    if contract.contract_type_id == contract.env.ref('l10n_pt_hr_payroll.contract_type_intern'):
        return True
    else:
        return False


def _get_extra_hours_entries(payslip, employee):
    hr_entry_type_extra_hours = payslip.env.ref('l10n_pt_hr_payroll.extra_hours_days_entry_type')
    if hr_entry_type_extra_hours:
        work_entries = payslip.env['hr.work.entry'].search([
            ('date_start', '<=', payslip.date_to),
            ('date_stop', '>=', payslip.date_from),
            ('employee_id', '=', employee.id),
            ('work_entry_type_id', '=', hr_entry_type_extra_hours.id)
        ])
    return work_entries


def calc_hours(contract, total_hours, rate):
    hour_value = (contract.wage * 12) / (52 * contract.resource_calendar_id.hours_per_week)

    total_value = (hour_value * total_hours) + (hour_value * total_hours * rate)
    return total_value


def get_week_days(payslip):
    hours = 0
    entries_discount = entries_to_discount_wage(payslip)
    for line in payslip.worked_days_line_ids.filtered(lambda w: w.is_correction):
        entries = payslip.env['hr.work.entry'].search([
            ('employee_id', '=', payslip.employee_id.id),
            ('work_entry_type_id', '=', line.work_entry_type_id.id),
            ('state', '=', 'draft')  # Only draft entries
        ])
        previous_entries = entries.filtered(lambda
                                                e: e.date_start.month < payslip.date_to.month and e.date_start.year == payslip.date_to.year or e.date_start.year < payslip.date_to.year)
        for e in previous_entries:
            if e.date_start.weekday() < 5:  # Only weekdays (Monday to Friday)
                # Apply negative sign for entries that discount
                if e.work_entry_type_id.code in entries_discount:
                    hours -= e.duration
                else:
                    hours += e.duration
    days = hours / payslip.version_id.resource_calendar_id.hours_per_day
    return days


def entries_to_discount_wage(payslip):
    return payslip.env['hr.work.entry.type'].search(
        [('discounts_salary', '=', True)]
    ).mapped('code')


def entries_considered_work(payslip):
    entries_considered_work = [payslip.env.ref('l10n_pt_hr_payroll.vacation_entry_type').code,
                               payslip.env.ref('hr_work_entry.work_entry_type_attendance').code]
    return entries_considered_work


def taxed_value_meal_allowance(contract, payslip):
    taxed_value = 0
    if contract.food == 'cartao' and contract.foodValue > payslip.env.company.default_hr_payroll_food_val_card_exempt_limit:
        taxed_value = contract.foodValue - payslip.env.company.default_hr_payroll_food_val_card_exempt_limit
    elif contract.food == 'normal' and contract.foodValue > payslip.env.company.default_hr_payroll_food_val_exempt_limit:
        taxed_value = contract.foodValue - payslip.env.company.default_hr_payroll_food_val_exempt_limit
    total = taxed_value * payslip.meal_allw_days
    return float(total)


def taxed_value_fail_allow(contract, categories, payslip):
    taxed_amount = 0
    if categories.get('FAIL_ALLOW'):
        exempt_value = ((contract.wage * 14) / 12) * 0.05
        taxed_amount += categories['FAIL_ALLOW'] - exempt_value
    if taxed_amount < 0:
        return 0
    return taxed_amount


def check_days_worked(payslip, employee, month, year):
    entire_month = True
    cal = calendar.monthrange(year, month)[1]
    first_day = payslip.date_from
    last_day = payslip.date_to
    if payslip.entries_date_from == first_day and payslip.entries_date_to == last_day:
        entire_month = True
        return entire_month
    else:
        entire_month = False
    for day in range(1, cal + 1):
        date = first_day + timedelta(days=day - 1)
        date_min = datetime.combine(date, datetime.min.time())
        date_max = datetime.combine(date, datetime.max.time())
        if not payslip.env['hr.work.entry'].search(
                [('employee_id', '=', employee.id), ('date_start', '>=', date_min), ('date_start', '<=', date_max)]):
            entire_month = False
    return entire_month


def get_ss_rate(contract):
    return contract.ss_regime.employee_rate


def _get_irs_tax_cease_chr(employee, payslip, contract):
    # correr recibos do ano corrente -> somar subsidio -> baseIH
    slips = payslip.env['hr.payslip'].search(
        [('state', 'in', ['done', 'paid']), ('employee_id', '=', employee.id)]).filtered(
        lambda s: s.date_to.year == payslip.date_to.year)
    total_chr_allw = contract.wage / 12 * (len(slips))
    return total_chr_allw


def _get_irs_tax_cease_vac(employee, payslip, contract):
    # correr recibos do ano corrente -> somar subsidio -> baseIH
    slips = payslip.env['hr.payslip'].search(
        [('state', 'in', ['done', 'paid']), ('employee_id', '=', employee.id)]).filtered(
        lambda s: s.date_to.year == payslip.date_to.year)
    total_vac_allw = contract.wage / 12 * (len(slips))
    return total_vac_allw


def compute_irs_allowances(contract, categories, employee, payslip, is_chr, is_vac, is_meal, baseIH):
    is_chr = is_chr or False
    is_vac = is_vac or False
    is_meal = is_meal or False

    if payslip.payslip_type == 'normal':
        baseIH = baseIH - categories['CORR']
    elif payslip.payslip_type == 'cease':
        if is_chr:
            baseIH = baseIH - categories['CORR'] + categories['CHRSUB']
        elif is_vac:
            baseIH = baseIH - categories['CORR'] + categories['VACSUB']

    def replace_and_evaluate(val, payment):
        if '%%VALUE%%' in val:
            val_with_payment = val.replace('%%VALUE%%', str(payment))
            return contract.make_eval(val_with_payment)
        return float(val)

    def get_tax_percentage(table_line, payment, depends):
        depends_val = 0
        parcel = 0
        parcel = replace_and_evaluate(table_line.to_be_deducted, payment)
        if depends >= 1:
            depends_val = depends * table_line.dependent_val
        percentage_val = (payment * table_line.marginal_rate) - parcel - depends_val
        percentage = (percentage_val * 100) / payment
        return percentage

    def find_element(val, table):
        for line in table.table_line_ids:
            if line.value > val:
                return line
        return None  # Retorna None se nenhum elemento for encontrado

    irs_table = payslip.env['irs.tax.table']
    table_category = 'H' if employee.pensioner else 'A'
    table = False
    if employee.disabled or employee.spouse_handycap or employee.dependent_handycap > 0:  # DEFICIENTE
        if employee.marital != 'married' or (
                employee.marital and employee.depending == 2) and employee.children == 0:  # Não casado ou casado dois titulares, sem dependentes - Deficiente
            irs_table = irs_table.search(
                [('code', '=', 'not_married_and_handicap_no_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital != 'married' and employee.children >= 1:  # Não casado, com um ou mais dependentes, deficiente
            irs_table = irs_table.search(
                [('code', '=', 'not_married_handicap_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital == 'married' and employee.depending == 2 and employee.children >= 1:  # Casado dois titulares, com um ou mais dependentes - deficiente
            irs_table = irs_table.search(
                [('code', '=', 'married_handicap_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital == 'married' and employee.depending == 1:  # Casado único titular - deficiente
            irs_table = irs_table.search(
                [('code', '=', 'married_unique_handicap'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)

    else:  # NÃO DEFICIENTE
        if employee.marital != 'married' and employee.children == 0 or (
                employee.marital and employee.depending == 2):  # Não casado ou casado dois titulares, sem dependentes
            irs_table = irs_table.search(
                [('code', '=', 'married_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital != 'married' and employee.children >= 1:  # Não casado, com um ou mais dependentes
            irs_table = irs_table.search(
                [('code', '=', 'not_married_and_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital == 'married' and employee.depending == 2 and employee.children >= 1:  # Casado dois titulares, com um ou mais dependentes
            irs_table = irs_table.search(
                [('code', '=', 'married_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital == 'married' and employee.depending == 1:  # Casado único titular
            irs_table = irs_table.search(
                [('code', '=', 'married_unique_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)

    if not table:
        raise ValidationError(f"No IRS table found for this PaySlip.\nMake sure PaySlip Processing Period and Income Locale are correct.")

    if is_chr:
        result_rate = employee.irs_monthly_tax_chr * 100 if employee.irs_monthly_tax_chr > 0 else get_tax_percentage(
            table, baseIH,
            employee.children)
    elif is_vac:
        result_rate = employee.irs_monthly_tax_vac * 100 if employee.irs_monthly_tax_vac > 0 else get_tax_percentage(
            table, baseIH,
            employee.children)
    else:
        result_rate = employee.irs_monthly_tax * 100 if employee.irs_monthly_tax > 0 else get_tax_percentage(table,
                                                                                                             baseIH,
                                                                                                             employee.children)
    taxed_value = 0
    result = 0
    if contract.food == 'cartao' and contract.foodValue > payslip.env.company.default_hr_payroll_food_val_card_exempt_limit:
        taxed_value = contract.foodValue - payslip.env.company.default_hr_payroll_food_val_card_exempt_limit
    elif contract.food == 'normal' and contract.foodValue > payslip.env.company.default_hr_payroll_food_val_exempt_limit:
        taxed_value = contract.foodValue - payslip.env.company.default_hr_payroll_food_val_exempt_limit
    taxed_value = taxed_value * payslip.meal_allw_days
    exempt_limit = 0
    if contract.youth_irs:
        monthly_limit = payslip.env.company.annual_youth_irs_limit / 14
        exempt_limit = baseIH
        if contract.income_years_declared == '1':
            exempt_limit = exempt_limit
        elif contract.income_years_declared == '0.75':
            exempt_limit = exempt_limit * 0.75
        elif contract.income_years_declared == '0.5':
            exempt_limit = exempt_limit * 0.5
        elif contract.income_years_declared == '0.25':
            exempt_limit = exempt_limit * 0.25
        exempt_limit = exempt_limit if exempt_limit <= monthly_limit else monthly_limit
    if is_chr:
        result = float(categories['CHRSUB'] - categories['CHR_CORR'])
        if contract.christmas == 'sem_dist':
            result = result - exempt_limit
        elif contract.christmas == 'com_dist_total':
            result = result - exempt_limit / 12
        elif contract.christmas == 'com_dist_metade':
            if contract.month_selection_chr != payslip.date_to.strftime('%m'):
                result = result - exempt_limit / 12 / 2
            else:
                result = result - exempt_limit / 2
    elif is_vac:
        result = float(categories['VACSUB'] - categories['VAC_CORR'])
        if contract.vacation == 'sem_dist':
            result = result - exempt_limit
        elif contract.vacation == 'com_dist_total':
            result = result - exempt_limit / 12
        elif contract.vacation == 'com_dist_metade':
            if contract.month_selection_vac != payslip.date_to.strftime('%m'):
                result = result - exempt_limit / 12 / 2
            else:
                result = result - exempt_limit / 2
    elif is_meal and taxed_value:
        result = float(taxed_value - categories['MEAL_CORR'])

    result_rate = result_rate if result_rate > 0 else 0
    result = result if result > 0 else 0
    # Don't round the amount - let Odoo round the total (amount * quantity)
    return result, round(result_rate, 2)


def compute_irs_wage(payslip, contract, categories, employee):
    def replace_and_evaluate(val, payment):
        if '%%VALUE%%' in val:
            val_with_payment = val.replace('%%VALUE%%', str(payment))
            return contract.make_eval(val_with_payment)
        return float(val)

    def get_tax_percentage(table_line, payment, depends):
        depends_val = 0
        parcel = 0
        parcel = replace_and_evaluate(table_line.to_be_deducted, payment)
        if depends >= 1:
            depends_val = depends * table_line.dependent_val
        percentage_val = (payment * table_line.marginal_rate) - parcel - depends_val
        percentage = (percentage_val * 100) / payment
        return percentage

    def find_element(val, table):
        for line in table.table_line_ids:
            if line.value > val:
                return line
        return None  # Retorna None se nenhum elemento for encontrado

    # valor base tributável do ordenado mensal
    if payslip.payslip_type == 'extraordinary':
        basic = get_previous_amount(payslip, 'BASIC')
        ih = get_previous_amount(payslip, 'IH')
        baseIH = basic + ih + categories['RETRO_IRS'] + categories['RETRO_IRS_SS']
    elif payslip.payslip_type == 'cease':
        baseIH = categories['BASIC'] + categories['BONUS_IRS'] + categories['BONUS_IRS_SS'] + categories['RETRO_IRS'] + categories['RETRO_IRS_SS'] + categories['TERM_COMP']
    else:
        baseIH = categories['BASIC'] + categories['BONUS_IRS'] + categories['BONUS_IRS_SS'] + categories['RETRO_IRS'] + categories['RETRO_IRS_SS']

    irs_table = payslip.env['irs.tax.table']
    table_category = 'H' if employee.pensioner else 'A'
    table = False

    if employee.disabled or employee.spouse_handycap or employee.dependent_handycap > 0:  # DEFICIENTE
        if (employee.marital != 'married' or
            employee.marital == 'married' and employee.depending == 2) and employee.children == 0:  # Não casado ou casado dois titulares, sem dependentes - Deficiente
            irs_table = irs_table.search(
                [('code', '=', 'not_married_and_handicap_no_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital != 'married' and employee.children >= 1:  # Não casado, com um ou mais dependentes, deficiente
            irs_table = irs_table.search(
                [('code', '=', 'not_married_handicap_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital == 'married' and employee.depending == 2 and employee.children >= 1:  # Casado dois titulares, com um ou mais dependentes - deficiente
            irs_table = irs_table.search(
                [('code', '=', 'married_handicap_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital == 'married' and employee.depending == 1:  # Casado único titular - deficiente
            irs_table = irs_table.search(
                [('code', '=', 'married_unique_handicap'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)

    else:  # NÃO DEFICIENTE
        if employee.marital != 'married' and employee.children == 0 or (
                employee.marital and employee.depending == 2):  # Não casado ou casado dois titulares, sem dependentes
            irs_table = irs_table.search(
                [('code', '=', 'married_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital != 'married' and employee.children >= 1:  # Não casado, com um ou mais dependentes
            irs_table = irs_table.search(
                [('code', '=', 'not_married_and_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital == 'married' and employee.depending == 2 and employee.children >= 1:  # Casado dois titulares, com um ou mais dependentes
            irs_table = irs_table.search(
                [('code', '=', 'married_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)
        elif employee.marital == 'married' and employee.depending == 1:  # Casado único titular
            irs_table = irs_table.search(
                [('code', '=', 'married_unique_with_dependents'), ('date_start', '<=', payslip.date_from),
                 ('date_end', '>=', payslip.date_to), ('income_locale', '=', payslip.income_locale),
                 ('category', '=', table_category)])
            table = find_element(baseIH, irs_table)

    if not table:
        raise ValidationError(f"No IRS table found for this PaySlip.\nMake sure PaySlip Processing Period and Income Locale are correct.")

    result_rate = employee.irs_monthly_tax * 100 if employee.irs_monthly_tax > 0 else get_tax_percentage(table, baseIH,
                                                                                                         employee.children)
    result_rate = round(result_rate, 2)
    result = float(
        categories['BASIC'] + categories['BONUS_IRS'] + categories['BONUS_IRS_SS'] + categories['RETRO_IRS'] + categories['RETRO_IRS_SS'] - categories['BASIC_CORR'])

    if payslip.payslip_type == 'cease':
        emp = payslip.env['hr.employee'].browse(payslip.employee_id.id)
        first_contract_year = emp._l10n_pt_get_first_contract_year() or payslip.date_from.year
        antiguity = payslip.date_from.year - first_contract_year
        antiguity = antiguity if antiguity > 0 else 1
        slips = payslip.env['hr.payslip'].search(
            [('employee_id', '=', employee.id), ('state', 'in', ['done', 'paid'])]).filtered(
            lambda s: s.date_from >= payslip.date_from + relativedelta(years=-1))
        cat_a_total = 0
        for slip in slips:
            for line in slip.line_ids.filtered(lambda l: l.salary_rule_id.category_id.code == 'BASIC'):
                cat_a_total += line.total
        cat_a_total = ((cat_a_total * antiguity) / 12)
        if categories['TERM_COMP']:
            if categories['TERM_COMP'] > cat_a_total:
                taxed_value = categories['TERM_COMP'] - cat_a_total
                result = result + taxed_value
    if categories['COST_ALLW']:
        if employee.moe:
            if contract.cost_allw_amount > payslip.env.company.default_hr_payroll_cost_allowance_moe_exempt_limit:
                input = categories['COST_ALLW'] / contract.cost_allw_amount
                taxed_amount = (
                                       contract.cost_allw_amount - payslip.env.company.default_hr_payroll_cost_allowance_moe_exempt_limit) * input
                result = result + taxed_amount
        elif contract.cost_allw_amount > payslip.env.company.default_hr_payroll_cost_allowance_exempt_limit:
            input = categories['COST_ALLW'] / contract.cost_allw_amount
            taxed_amount = (
                                   contract.cost_allw_amount - payslip.env.company.default_hr_payroll_cost_allowance_exempt_limit) * input
            result = result + taxed_amount
    if categories['AC_FOREIGN']:
        if employee.moe:
            if contract.cost_allw_amount_foreign > payslip.env.company.default_hr_payroll_foreign_cost_allowance_moe_exempt_limit:
                input = categories['AC_FOREIGN'] / contract.cost_allw_amount_foreign
                taxed_amount = (
                                       contract.cost_allw_amount_foreign - payslip.env.company.default_hr_payroll_foreign_cost_allowance_moe_exempt_limit) * input
                result = result + taxed_amount
        elif contract.cost_allw_amount_foreign > payslip.env.company.default_hr_payroll_foreign_cost_allowance_exempt_limit:
            input = categories['AC_FOREIGN'] / contract.cost_allw_amount_foreign
            taxed_amount = (
                                   contract.cost_allw_amount_foreign - payslip.env.company.default_hr_payroll_foreign_cost_allowance_exempt_limit) * input
            result = result + taxed_amount
    if categories['KMS']:
        if contract.km_value > payslip.env.company.default_hr_payroll_km_exempt_limit:
            input = categories['KMS'] / contract.km_value
            taxed_amount = (contract.km_value - payslip.env.company.default_hr_payroll_km_exempt_limit) * input
            result = result + taxed_amount
    if categories['PERF_BONUS']:
        exempt_amount = contract.wage * 0.06
        if categories['PERF_BONUS'] > exempt_amount:
            taxed_amount = categories['PERF_BONUS'] - exempt_amount
            result += taxed_amount
    if categories['FAIL_ALLOW']:
        exempt_value = ((contract.wage * 14) / 12) * 0.05
        taxed_amount = categories['FAIL_ALLOW'] - exempt_value
        if taxed_amount < 0:
            taxed_amount = 0
        result += taxed_amount

    if contract.youth_irs:
        monthly_limit = payslip.env.company.annual_youth_irs_limit / 14
        exempt_limit = categories['BASIC'] + categories['BONUS_IRS'] + categories['BONUS_IRS_SS'] + categories['RETRO_IRS'] + categories['RETRO_IRS_SS'] + categories['OTHER_IRS']
        if contract.income_years_declared == '1':
            exempt_limit = exempt_limit
        elif contract.income_years_declared == '0.75':
            exempt_limit = exempt_limit * 0.75
        elif contract.income_years_declared == '0.5':
            exempt_limit = exempt_limit * 0.5
        elif contract.income_years_declared == '0.25':
            exempt_limit = exempt_limit * 0.25
        exempt_limit = exempt_limit if exempt_limit <= monthly_limit else monthly_limit
        result = result - exempt_limit
    result_rate = result_rate if result_rate > 0 else 0
    result = result if result > 0 else 0
    # Don't round the amount - let Odoo round the total (amount * quantity)
    return result, result_rate


class PayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    retroactive_id = fields.Many2one('hr.payroll.retroactive', string='Retroactive Adjustment')
    retroactive_line_id = fields.Many2one('hr.payroll.retroactive.line', string='Retroactive Line')
    origin_month = fields.Date(string='Origin Month')
    payment_month = fields.Date(string='Payment Month')
    natrem_code = fields.Char(string='NATREM Code')
    communication_state = fields.Selection([
        ('to_communicate', 'To Communicate'),
        ('communicated', 'Communicated'),
        ('error', 'Error'),
        ('excluded', 'Excluded'),
    ], default='to_communicate')

    def _get_line_name(self):
        input_line = self.slip_id.input_line_ids.filtered(lambda l: l.code == self.salary_rule_id.code)[:1]
        return input_line.name or self.name

    def _get_line_value(self):
        if self.salary_rule_id.code == 'BASIC':
            if self._get_line_quantity() == 30:
                return self.total
            else:
                return float_round((self.slip_id.version_id.wage / 30) * self._get_line_quantity(), 2)
        elif self.salary_rule_id.code == 'IH':
            # Schedule exemption should also reflect period days when there's discount
            if self.slip_id.discount_amount and self.slip_id.version_id.exemption_schedule:
                days = self._get_line_quantity()
                exemption_value = self.slip_id.version_id.wage * self.slip_id.version_id.exemption_schedule_percentage
                return float_round((exemption_value / 30) * days, 2)
        # Default: return the line total
        return self.total if self.total else 0.0

    def _get_line_quantity(self):
        inputs = []
        if self.salary_rule_id.code in ['BASIC', 'IH']:
            if self.slip_id.discount_amount:
                # Calculate days based on entries period (e.g., 01-11 to 20-11 = 20 days)
                # Maximum 30 days for months with 31 days
                days_in_period = (self.slip_id.entries_date_to - self.slip_id.entries_date_from).days + 1
                return min(days_in_period, 30)
            return self.slip_id.days_worked
        for input in self.slip_id.input_line_ids:
            inputs.append(input.code)
        if self.salary_rule_id.show_qty_in_pdf:
            return self.quantity
        elif self.salary_rule_id.code in inputs and self.salary_rule_id.code not in ['TN',
                                                                                     'HD'] or self.salary_rule_id.code in [
            'PROP_SF', 'PROP_SN']:
            return 0
        elif not self.salary_rule_id.show_qty_in_pdf:
            return 0
        else:
            return 30

    def create(self, vals_list):
        res = super(PayslipLine, self).create(vals_list)
        irs_ded_category = self.env.ref('l10n_pt_hr_payroll.hr_payroll_irs_ded', raise_if_not_found=False)
        if irs_ded_category:
            for line in res:
                if line.salary_rule_id.category_id == irs_ded_category:
                    line.total = int(float(line.quantity) * line.amount * line.rate / 100)
        return res
