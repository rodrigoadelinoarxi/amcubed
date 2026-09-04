from odoo import models, fields, api


class UniqueReportTable4(models.AbstractModel):
    _name = 'unique.report.table.mixin'
    _description = 'Unique Report Table Mixin'

    name = fields.Char(string='Name')
    code = fields.Char(string='Code')
    _rec_name = 'display_name'

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code} - {record.name}"


class UniqueReportTable3(models.Model):
    _name = 'unique.report.table.3'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 3 - Municipalities-Parishes'

class UniqueReportTable4(models.Model):
    _name = 'unique.report.table.4'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 4 - CAE'

class UniqueReportTable5(models.Model):
    _name = 'unique.report.table.5'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 5 - Company Status'


class UniqueReportTable6(models.Model):
    _name = 'unique.report.table.6'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 6 - Company Status Reason'

class UniqueReportTable7(models.Model):
    _name = 'unique.report.table.7'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 7 - Legal Nature'

class UniqueReportTable8(models.Model):
    _name = 'unique.report.table.8'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 8 - Employer Association'

class UniqueReportTable9(models.Model):
    _name = 'unique.report.table.9'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 9 - Charge Origin'

class UniqueReportTable10(models.Model):
    _name = 'unique.report.table.10'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 10 - Not Worked Hours Reason'

class UniqueReportTable11(models.Model):
    _name = 'unique.report.table.11'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 11 - Applied Retirement Regimen'


class UniqueReportTable13(models.Model):
    _name = 'unique.report.table.13'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 13 - Contract Type'


class UniqueReportTable14(models.Model):
    _name = 'unique.report.table.14'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 14 - Literary Qualification Type'


class UniqueReportTable15(models.Model):
    _name = 'unique.report.table.15'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 15 - Job Situation'


class UniqueReportTable16(models.Model):
    _name = 'unique.report.table.16'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 16 - Jobs'


class UniqueReportTable19(models.Model):
    _name = 'unique.report.table.19'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 19 - IRCT Applicability'


class UniqueReportTable21(models.Model):
    _name = 'unique.report.table.21'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 21 - Qualification Level'


class UniqueReportTable22(models.Model):
    _name = 'unique.report.table.22'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 22 - Work Duration Regimen'

class UniqueReportTable23(models.Model):
    _name = 'unique.report.table.23'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 23 - Working Time Duration'

class UniqueReportTable24(models.Model):
    _name = 'unique.report.table.24'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 24 - Working Time Organization'

class UniqueReportTable25(models.Model):
    _name = 'unique.report.table.25'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 25 - Non Paid Hours Reason'

class UniqueReportTable26(models.Model):
    _name = 'unique.report.table.26'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 26 - Company Entry Reason'

class UniqueReportTable27(models.Model):
    _name = 'unique.report.table.27'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 27 - Company Exit Reason'

class UniqueReportTable28(models.Model):
    _name = 'unique.report.table.28'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 28 - Training Frequency'

class UniqueReportTable29(models.Model):
    _name = 'unique.report.table.29'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 29 - Training Reference Period'

class UniqueReportTable30(models.Model):
    _name = 'unique.report.table.30'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 30 - Training Area'

class UniqueReportTable31(models.Model):
    _name = 'unique.report.table.31'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 31 - Training Type'

class UniqueReportTable32(models.Model):
    _name = 'unique.report.table.32'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 32 - Training Initiative'

class UniqueReportTable33(models.Model):
    _name = 'unique.report.table.33'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 33 - Training Schedule'

class UniqueReportTable34(models.Model):
    _name = 'unique.report.table.34'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 34 - Training Entity'

class UniqueReportTable35(models.Model):
    _name = 'unique.report.table.35'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 35 - Certificate Type'

class UniqueReportTable36(models.Model):
    _name = 'unique.report.table.36'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 36 - Training Qualification Level'

class UniqueReportTable52(models.Model):
    _name = 'unique.report.table.52'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 52 - Claim'

class UniqueReportTable53(models.Model):
    _name = 'unique.report.table.53'
    _inherit = 'unique.report.table.mixin'
    _description = 'Unique Report Table 53 - Claim Result'



