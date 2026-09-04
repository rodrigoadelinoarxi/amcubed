from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    social_security_regimen = fields.Many2one('unique.report.table.11', string='Social Security Regimen')
    last_promotion_date = fields.Date(string='Last Promotion Date')
    literacy_habilitations = fields.Many2one('unique.report.table.14', string='Literacy Habilitations')
    job_situation = fields.Many2one('unique.report.table.15', string='Employee Job Situation')
    job_ur = fields.Many2one('unique.report.table.16', string='Employee Job')
    irct_regulation = fields.Char(string='IRCT Regulation')
    irct_applicability = fields.Many2one('unique.report.table.19', string='IRCT Applicability')
    job_category = fields.Char(string='Professional Category')
    qualification_level = fields.Many2one('unique.report.table.21', string='Qualification Level')
    work_duration_regimen = fields.Many2one('unique.report.table.22', string='Work Duration Regimen')
    working_time_duration = fields.Many2one('unique.report.table.23', string='Working Time Duration')
    working_time_organization = fields.Many2one('unique.report.table.24', string='Working Time Organization')
    training_history_ids = fields.One2many('hr.employee.training.history', 'employee_id',
                                           string='Training History')

    def compute_training_hours(self):
        training_type = self.env.ref('l10n_pt_hr_payroll.training_time_off_status')
        for employee in self:
            # Buscar ausências de formação
            time_offs = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', training_type.id),
                ('state', '=', 'validate')
            ])
            # Agrupar horas por ano
            hours_per_year = {}
            for leave in time_offs:
                year = leave.date_from.year
                duration = leave.number_of_hours or 0.0
                hours_per_year[year] = hours_per_year.get(year, 0.0) + duration

            # Atualizar apenas anos com dados
            for year, hours in hours_per_year.items():
                history = self.env['hr.employee.training.history'].search([
                    ('employee_id', '=', employee.id),
                    ('year', '=', year)
                ], limit=1)

                if history:
                    history.training_hours = hours
                else:
                    self.env['hr.employee.training.history'].create({
                        'employee_id': employee.id,
                        'year': year,
                        'training_hours': hours
                    })

class EmployeeTrainingHistory(models.Model):
    _name = 'hr.employee.training.history'
    _description = 'Histórico de Formação do Funcionário'
    _order = 'year desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    year = fields.Integer(string='Year', required=True)
    training_hours = fields.Float(string='Training Hours', required=True)
