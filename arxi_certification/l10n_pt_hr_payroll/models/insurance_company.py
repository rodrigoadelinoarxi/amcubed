# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrInsuranceCompany(models.Model):
    _name = 'hr.insurance.company'
    _description = 'Insurance Company'
    _order = 'code'
    _rec_name = 'display_name'

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    code = fields.Char(string='Code', required=True, index=True)
    name = fields.Char(string='Name', required=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code} - {record.name}"

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
