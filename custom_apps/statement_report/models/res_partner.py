# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author:Jumana Haseen (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import base64
import io
import json
import xlsxwriter
from odoo import fields, models
from odoo.exceptions import ValidationError
from odoo.tools import date_utils


class Partner(models.Model):
    """ Class for adding report options  in 'res.partner' """
    _inherit = 'res.partner'

    customer_report_ids = fields.Many2many(
        'account.move',
        compute='_compute_customer_report_ids',
        help='Partner Invoices related to Customer')
    vendor_statement_ids = fields.Many2many(
        'account.move',
        compute='_compute_vendor_statement_ids',
        help='Partner Bills related to Vendor')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id.id,
        help="currency related to Customer or Vendor"
    )

    def _compute_customer_report_ids(self):
        """ For computing 'invoices' of partner"""
        for rec in self:
            inv_ids = self.env['account.move'].search(
                [('partner_id', '=', rec.id),
                 ('move_type', '=', 'out_invoice'),
                 ('payment_state', '!=', 'paid'),
                 ('state', '=', 'posted')])
            rec.customer_report_ids = inv_ids

    def _compute_vendor_statement_ids(self):
        """ For computing 'bills' of partner """
        for rec in self:
            bills = self.env['account.move'].search(
                [('partner_id', '=', rec.id),
                 ('move_type', '=', 'in_invoice'),
                 ('payment_state', '!=', 'paid'),
                 ('state', '=', 'posted')])
            rec.vendor_statement_ids = bills

    def main_query(self):
        """Return select query"""
        query = """SELECT name , invoice_date, invoice_date_due,
                    amount_total_signed AS sub_total,
                    amount_residual_signed AS amount_due ,
                    amount_residual AS balance
            FROM account_move WHERE payment_state != 'paid'
            AND state ='posted' AND partner_id= '%s'
            AND company_id = '%s' """ % (self.id, self.env.company.id)
        return query

    def amount_query(self):
        """Return query for calculating total amount"""
        amount_query = """ SELECT SUM(amount_total_signed) AS total, 
                    SUM(amount_residual) AS balance
                FROM account_move WHERE payment_state != 'paid' 
                AND state ='posted' AND partner_id= '%s'
                AND company_id = '%s' """ % (self.id, self.env.company.id)
        return amount_query

    def action_print_pdf(self):
        """ Action for printing pdf report"""
        if self.customer_report_ids:
            # Query to fetch all unpaid invoices
            main_query = self.main_query()
            main_query += """ AND move_type IN ('out_invoice') ORDER BY invoice_date ASC"""
            self.env.cr.execute(main_query)
            invoices = self.env.cr.dictfetchall()

            # Calculate cumulative total (running balance)
            running_balance = 0
            for invoice in invoices:
                # Add cumulative balance for each invoice
                running_balance += invoice['balance']
                invoice['cumulative_balance'] = running_balance

            # Update the total amount query
            amount_query = self.amount_query()
            amount_query += """ AND move_type IN ('out_invoice')"""
            self.env.cr.execute(amount_query)
            amount = self.env.cr.dictfetchall()

            # Prepare data for the report
            data = {
                'customer' : self.display_name,
                'street'   : self.street,
                'street2'  : self.street2,
                'city'     : self.city,
                'state'    : self.state_id.name,
                'zip'      : self.zip,
                'my_data'  : invoices,  # Use the updated invoices with cumulative balances
                'total'    : amount[0]['total'],
                'balance'  : amount[0]['balance'],
                'total_sum': running_balance,  # Include the final running balance
                'currency' : self.currency_id.symbol,
            }
            return self.env.ref('statement_report.res_partner_action').report_action(self, data=data)
        else:
            raise ValidationError('There is no statement to print')

    def action_vendor_print_pdf(self):
        """ Action for printing vendor pdf report """
        if self.vendor_statement_ids:
            main_query = self.main_query()
            main_query += """ AND move_type IN ('in_invoice') ORDER BY invoice_date ASC"""
            amount = self.amount_query()
            amount += """ AND move_type IN ('in_invoice')"""

            self.env.cr.execute(main_query)
            invoices = self.env.cr.dictfetchall()

            # Calculate cumulative total (running balance)
            running_balance = 0
            for invoice in invoices:
                # Add cumulative balance for each invoice
                running_balance += invoice['balance']
                invoice['cumulative_balance'] = running_balance

            self.env.cr.execute(amount)
            amount = self.env.cr.dictfetchall()
            data = {
                'customer': self.display_name,
                'street': self.street,
                'street2': self.street2,
                'city': self.city,
                'state': self.state_id.name,
                'zip': self.zip,
                # 'my_data': main,
                'my_data': invoices,
                'total': amount[0]['total'],
                'balance': amount[0]['balance'],
                'total_sum': running_balance,
                'currency': self.currency_id.symbol,
            }
            return self.env.ref(
                'statement_report.res_partner_action').report_action(
                self, data=data)
        else:
            raise ValidationError('There is no statement to print')