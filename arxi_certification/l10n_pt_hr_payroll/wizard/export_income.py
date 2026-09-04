import base64
import unicodedata
import calendar

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

from odoo.tools import float_round
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)

ENTRIES_WORK = ['WORK100', 'VACATION']


class ExportIncome(models.TransientModel):
    _name = 'export.income.wizard'
    _inherit = 'export.income.deduction.mixin'
    _description = 'Wizard to export Income File'

    def _get_filter_domain(self, lines):
        return lines.filtered(
            lambda l: l.salary_rule_id.category_id.code not in ['DED', 'GROSS', 'NET', 'EE', 'IRS'] and l.total > 0)

    def _get_filename(self):
        return f"Income_Report_{self.date_start.strftime('%Y-%m-%d')}_{self.date_end.strftime('%Y-%m-%d')}.pdf".replace(
            ' ', '_')

    def _get_title(self):
        return _('Income Report')
