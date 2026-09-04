from odoo import models, fields, _
from dateutil.relativedelta import relativedelta
import logging
import base64

_logger = logging.getLogger(__name__)


class ExportIncomeDeductionMixin(models.AbstractModel):
    _name = 'export.income.deduction.mixin'
    _description = 'Mixin for Export Income and Deduction'

    date_start = fields.Date(
        string='Start Date',
        default=fields.Date.today().replace(month=fields.Date.today().month, day=1) - relativedelta(months=1))
    date_end = fields.Date(
        string='End Date',
        default=fields.Date.today().replace(day=1) - relativedelta(days=1))

    date_start = fields.Date(
        string='Start Date',
        default=lambda self: fields.Date.today().replace(day=1) - relativedelta(months=1)
    )
    date_end = fields.Date(
        string='End Date',
        default=lambda self: fields.Date.today().replace(day=1) - relativedelta(days=1)
    )

    def _get_filter_domain(self, lines):
        raise NotImplementedError("Each subclass must implement `_get_filter_domain`.")

    def _get_filename(self):
        raise NotImplementedError("Each subclass must implement `_get_filename`.")

    def execute(self):
        lines = self.env['hr.payslip.line'].search([
            ('slip_id.date_to', '<=', self.date_end),
            ('slip_id.date_from', '>=', self.date_start),
            ('slip_id.state', 'in', ['done', 'paid']),
        ]).filtered(lambda l: l.slip_id.date_to.year == self.date_end.year)

        lines = self._get_filter_domain(lines)

        if not lines:
            _logger.info("No payslip lines found for export.")
            return

        context = dict(self.env.context, active_ids=lines.ids)
        data = self.with_context(context).process_payslips()
        data['report_title'] = self._get_title()

        report_pdf = self.env.ref('l10n_pt_hr_payroll.action_export_income_report')._render_qweb_pdf(
            'l10n_pt_hr_payroll.action_export_income_report',
            lines.ids,
            data=data
        )[0]

        filename = self._get_filename()

        attachment = self.env['ir.attachment'].create({
            'name'    : filename,
            'datas'   : base64.b64encode(report_pdf),
            'mimetype': 'application/pdf'
        })

        return {
            "type" : "ir.actions.act_url",
            "url"  : f"/web/content/{attachment.id}?download=true",
            "close": True,
        }

    def process_payslips(self):
        active_ids = self.env.context.get('active_ids', [])
        lines = self.env['hr.payslip.line'].browse(active_ids)

        grouped_data = {}
        for line in lines:
            rule = line.salary_rule_id.name
            employee = line.employee_id.name or 'No Employee'
            quantity = line.quantity if line.quantity > 1 else '-'

            grouped_data.setdefault(rule, {}).setdefault(employee, []).append({
                'rule'    : rule,
                'employee': employee,
                'name'    : line.name,
                'quantity': quantity,
                'value'   : line.total,
            })

        return {'grouped_lines': grouped_data}
