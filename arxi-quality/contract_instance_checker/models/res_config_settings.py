# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api
from .contract_instance_status import NO_USER_INFO_TYPES

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """
    Extension of settings for instance checker parameters.
    """
    _inherit = 'res.config.settings'

    instance_nif = fields.Char(
        string='Instance NIF',
        related='company_id.contract_nif',
        readonly=False,
        help='Company NIF for contract validation with the central server'
    )

    instance_token = fields.Char(
        string='Contract Code',
        related='company_id.contract_token',
        readonly=False,
        help='Access token provided by the central server'
    )

    central_server_url = fields.Char(
        string='Central Server URL',
        config_parameter='contract_instance_checker.central_server_url',
        default='https://contract.arxi.pt',
        help='Central server URL for contract validation (e.g. https://contract.arxi.pt)'
    )

    # Informational fields (read-only)
    last_check_date = fields.Datetime(
        string='Last Validation',
        compute='_compute_contract_status',
        help='Last contract check date'
    )

    contract_status = fields.Selection(
        [
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('error', 'Error'),
            ('not_found', 'Not Found'),
        ],
        string='Contract Status',
        compute='_compute_contract_status',
        help='Current contract status'
    )

    contract_end_date = fields.Date(
        string='Contract End Date',
        compute='_compute_contract_status',
        help='Contract expiration date'
    )

    user_limit = fields.Integer(
        string='User Limit',
        compute='_compute_contract_status',
        help='Maximum number of allowed users'
    )

    current_user_count = fields.Integer(
        string='Current User Count',
        compute='_compute_contract_status',
        help='Number of active users'
    )

    days_until_expiration = fields.Integer(
        string='Days Until Expiration',
        compute='_compute_contract_status',
        help='Days remaining until expiration'
    )

    # Helper fields for view conditions
    is_contract_ok = fields.Boolean(
        string='Contract OK',
        compute='_compute_contract_status',
        help='True if contract is active, not expiring soon and does not exceed user limit'
    )

    is_expiring_soon = fields.Boolean(
        string='Expiring Soon',
        compute='_compute_contract_status',
        help='True if contract is active but expires in less than 30 days'
    )

    is_user_limit_exceeded = fields.Boolean(
        string='User Limit Exceeded',
        compute='_compute_contract_status',
        help='True if number of users exceeds the limit'
    )

    contract_type = fields.Char(
        string='Contract Type',
        compute='_compute_contract_status',
    )

    show_user_info = fields.Boolean(
        string='Show User Info',
        compute='_compute_contract_status',
        help='False for certification/payroll/accounting contracts where user count is irrelevant',
    )

    hide_contract_danger = fields.Boolean(
        string='Hide Contract Danger Alert',
        compute='_compute_hide_contract_danger',
    )

    def _compute_hide_contract_danger(self):
        neutralized = bool(self.env['ir.config_parameter'].sudo().get_param('database.is_neutralized', False))
        in_debug = self.env.user.has_group('base.group_no_one')
        hide = neutralized and not in_debug
        for record in self:
            record.hide_contract_danger = hide

    def _compute_contract_status(self):
        """Load information from the last validation status"""
        # Force recomputation every time by not using @api.depends
        for record in self:
            latest_status = self.env['contract.instance.status'].sudo().get_latest_status()

            if latest_status:
                record.last_check_date = latest_status.last_check_date
                record.contract_status = latest_status.contract_status
                record.contract_end_date = latest_status.end_date
                record.user_limit = latest_status.user_limit
                record.current_user_count = latest_status.current_user_count
                record.days_until_expiration = latest_status.days_until_expiration

                # Compute contract_type and show_user_info first (used by helpers below)
                record.contract_type = record.company_id.contract_type or latest_status.contract_type or ''
                record.show_user_info = record.contract_type not in NO_USER_INFO_TYPES

                # Compute helper fields
                record.is_contract_ok = (
                    latest_status.contract_status == 'active' and
                    latest_status.days_until_expiration > 30 and
                    (not record.show_user_info or latest_status.current_user_count <= latest_status.user_limit)
                )
                record.is_expiring_soon = (
                    latest_status.contract_status == 'active' and
                    latest_status.days_until_expiration <= 30
                )
                record.is_user_limit_exceeded = (
                    latest_status.contract_status == 'active' and
                    latest_status.current_user_count > latest_status.user_limit
                )
                _logger.info(
                    '_compute_contract_status: company=%s, company.contract_type=%r, '
                    'status.contract_type=%r, effective=%r, show_user_info=%s, '
                    'NO_USER_INFO_TYPES=%s',
                    record.company_id.name, record.company_id.contract_type,
                    latest_status.contract_type, record.contract_type,
                    record.show_user_info, NO_USER_INFO_TYPES
                )
            else:
                record.last_check_date = False
                record.contract_status = False
                record.contract_end_date = False
                record.user_limit = 0
                record.current_user_count = 0
                record.days_until_expiration = 0
                record.is_contract_ok = False
                record.is_expiring_soon = False
                record.is_user_limit_exceeded = False
                record.contract_type = record.company_id.contract_type or ''
                record.show_user_info = record.contract_type not in NO_USER_INFO_TYPES

    @api.model
    def default_get(self, fields_list):
        """Override to force computation of contract status fields on load"""
        res = super(ResConfigSettings, self).default_get(fields_list)

        # Force load latest status
        latest_status = self.env['contract.instance.status'].sudo().get_latest_status()

        if latest_status:
            if 'last_check_date' in fields_list:
                res['last_check_date'] = latest_status.last_check_date
            if 'contract_status' in fields_list:
                res['contract_status'] = latest_status.contract_status
            if 'contract_end_date' in fields_list:
                res['contract_end_date'] = latest_status.end_date
            if 'user_limit' in fields_list:
                res['user_limit'] = latest_status.user_limit
            if 'current_user_count' in fields_list:
                res['current_user_count'] = latest_status.current_user_count
            if 'days_until_expiration' in fields_list:
                res['days_until_expiration'] = latest_status.days_until_expiration

            # Compute contract_type and show_user_info first (used by helpers below)
            if 'contract_type' in fields_list:
                res['contract_type'] = self.env.company.contract_type or latest_status.contract_type or ''
            effective_ct = res.get('contract_type', self.env.company.contract_type or latest_status.contract_type or '')
            show_user = effective_ct not in NO_USER_INFO_TYPES
            if 'show_user_info' in fields_list:
                res['show_user_info'] = show_user

            # Compute helper fields
            if 'is_contract_ok' in fields_list:
                res['is_contract_ok'] = (
                    latest_status.contract_status == 'active' and
                    latest_status.days_until_expiration > 30 and
                    (not show_user or latest_status.current_user_count <= latest_status.user_limit)
                )
            if 'is_expiring_soon' in fields_list:
                res['is_expiring_soon'] = (
                    latest_status.contract_status == 'active' and
                    latest_status.days_until_expiration <= 30
                )
            if 'is_user_limit_exceeded' in fields_list:
                res['is_user_limit_exceeded'] = (
                    latest_status.contract_status == 'active' and
                    latest_status.current_user_count > latest_status.user_limit
                )
            _logger.info(
                'default_get (with status): contract_type=%r, show_user_info=%s, '
                'company.contract_type=%r, status.contract_type=%r',
                res.get('contract_type'), res.get('show_user_info'),
                self.env.company.contract_type, latest_status.contract_type
            )
        else:
            if 'contract_type' in fields_list:
                res['contract_type'] = self.env.company.contract_type or ''
            if 'show_user_info' in fields_list:
                ct = res.get('contract_type', '')
                res['show_user_info'] = ct not in NO_USER_INFO_TYPES

        if 'hide_contract_danger' in fields_list:
            neutralized = bool(self.env['ir.config_parameter'].sudo().get_param('database.is_neutralized', False))
            in_debug = self.env.user.has_group('base.group_no_one')
            res['hide_contract_danger'] = neutralized and not in_debug

        return res

    def action_validate_now(self):
        """Action to force immediate validation for current company"""
        self.ensure_one()

        # Execute validation for current company directly
        self.env['contract.instance.status']._validate_contract_for_company(self.env.company)

        # Reload the view to show updated status
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
