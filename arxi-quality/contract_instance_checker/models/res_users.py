# -*- coding: utf-8 -*-

import logging
from odoo import models, api
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """
    Extensão do modelo res.users para implementar bloqueio de instância.
    Intercepts authentication to block access when contract expired.
    """
    _inherit = 'res.users'

    @api.model
    def _check_contract_before_login(self):
        """
        Verifica se a instância está bloqueada antes de permitir login.
        Raises AccessDenied if contract is expired and block_instance=True.
        """
        # Allow access to superuser (OdooBot and system users)
        if self.env.uid in [self.env.ref('base.user_admin').id, self.env.ref('base.user_root').id]:
            return True

        # Verificar se instância está bloqueada
        instance_status = self.env['contract.instance.status'].sudo()

        if instance_status.check_instance_blocked():
            block_message = instance_status.get_block_message()
            _logger.warning(f'Login blocked for user {self.env.uid}: {block_message}')
            raise AccessDenied(block_message)

        return True

    def _check_credentials(self, credential, env):
        """Override: add the contract verification after credential validation.

        Signature follows Odoo 18/19: ``credential`` is the credential dict
        ({'login', 'password'/'token', 'type'}), not a plain password.

        :param credential: credential dict from the auth flow
        :param env: request environment info dict
        :return: auth info dict from the base method
        :raises AccessDenied: when the instance contract blocks the login
        """
        # First validate the credentials normally
        result = super()._check_credentials(credential, env)

        # Then check contract (only if credentials valid)
        # Use sudo() to ensure check works for all users
        self.sudo()._check_contract_before_login()

        return result
