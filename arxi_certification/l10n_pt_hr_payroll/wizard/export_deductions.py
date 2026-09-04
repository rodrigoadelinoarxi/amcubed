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

class ExportDeductions(models.TransientModel):
    _name = 'export.deductions.wizard'
    _inherit = 'export.income.deduction.mixin'
    _description = 'Wizard to export Deductions File'

    def _get_filter_domain(self, lines):
        return lines.filtered(lambda l: (l.salary_rule_id.category_id.code in ['DED', 'IRS'] or l.total < 0) and l.total != 0)

    def _get_filename(self):
        return f"Deductions_Report_{self.date_start.strftime('%Y-%m-%d')}_{self.date_end.strftime('%Y-%m-%d')}.pdf".replace(' ', '_')

    def _get_title(self):
        return _('Deduction Report')  # ou Deduction Report consoante o wizard


