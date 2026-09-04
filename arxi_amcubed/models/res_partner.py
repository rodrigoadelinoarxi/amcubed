from odoo import models, fields, _, api
from odoo.exceptions import ValidationError
import re

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vat_normalized = fields.Char(
        compute='_compute_vat_normalized',
        store=True,
    )

    @api.depends('vat')
    def _compute_vat_normalized(self):
        for record in self:
            record.vat_normalized = re.sub(r'\D', '', record.vat or '')

    @api.constrains('vat')
    def _check_unique_vat(self):
        for record in self:

            if not record.vat:
                continue

            digits_vat = re.sub(r'\D', '', record.vat or '')

            # Collect all IDs in the same company hierarchy to exclude
            excluded_ids = record.ids
            if record.parent_id:
                excluded_ids += record.parent_id.ids
                excluded_ids += record.parent_id.child_ids.ids
            elif record.child_ids:
                excluded_ids += record.child_ids.ids

            duplicate = self.env['res.partner'].search([
                ('vat', '!=', False),
                ('vat_normalized', '=', digits_vat),
                ('id', 'not in', excluded_ids),
            ], limit=1)

            if duplicate:
                raise ValidationError(
                    _('VAT %(vat)s already exists on partner %(partner)s') % {
                        'vat': record.vat,
                        'partner': duplicate.name,
                    })