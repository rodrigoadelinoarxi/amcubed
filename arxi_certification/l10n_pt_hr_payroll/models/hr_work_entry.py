from odoo import models, fields


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    def _mark_leaves_outside_schedule(self):
        res = super()._mark_leaves_outside_schedule()
        work_entries = self._get_leaves_entries_outside_schedule()
        if work_entries := work_entries.filtered(lambda e: e.work_entry_type_id.request_days_in_a_row == 'calendar'):
            work_entries.update({'state': 'draft'})
            return False
        return res

    def _check_if_error(self):
        res = super()._check_if_error()
        outside_calendar = self.filtered(
            lambda e: e.work_entry_type_id.request_days_in_a_row == 'work')._mark_leaves_outside_schedule()
        return res or outside_calendar


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    request_days_in_a_row = fields.Selection([
        ('calendar', 'Calendar Days'),
        ('work', 'Work Days')
    ], default='work')

    discounts_salary = fields.Boolean(
        help="Mark if this work entry type should deduct from salary calculations.",
        default=False,
    )
