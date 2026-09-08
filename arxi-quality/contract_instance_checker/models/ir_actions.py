# -*- coding: utf-8 -*-

import logging
from odoo import api, models
from odoo.exceptions import AccessError
from odoo.http import request

_logger = logging.getLogger(__name__)


class IrActionsActions(models.Model):
    _inherit = "ir.actions.actions"

    @api.model
    def _get_latest_contract_status(self):
        env = request.env if request else self.env
        company = env.company
        latest_status = env["contract.instance.status"].get_latest_status(
            company=company
        )
        if not latest_status:
            _logger.debug(
                "Action guard: no status for company_id=%s company=%s",
                company.id,
                company.name,
            )
            return None
        return latest_status

    @api.model
    def _is_accounting_contract_blocked(self, status):
        return (
            status.contract_status in ("expired", "not_found")
            and status.contract_type == "accounting"
        )

    @api.model
    def _is_certification_contract_blocked(self, status):
        return (
            status.contract_status in ("expired", "not_found")
            and status.contract_type == "certification"
        )

    @api.model
    def _get_blocked_action_ids(self, menu_xml_ids):
        blocked_action_ids = set()
        for menu_xml_id in menu_xml_ids:
            menu = self.env.ref(menu_xml_id, raise_if_not_found=False)
            if menu and menu.action:
                blocked_action_ids.add(menu.action.sudo().id)
        return blocked_action_ids

    @api.model
    def _should_guard_action_load(self):
        if not request:
            return False
        if request.httprequest.path not in (
            "/web/action/load",
            "/web/action/load_breadcrumbs",
        ):
            return False
        return True

    def _raise_if_contract_action_blocked(self):
        if not self._should_guard_action_load():
            return

        is_neutralized = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("database.is_neutralized", False)
        )
        if is_neutralized:
            return

        status = self._get_latest_contract_status()
        if not status:
            return

        from .ir_ui_menu import INACTIVE_FREE_BLOCKED_MENUS, CERT_BLOCKED_MENUS

        blocked_action_ids = set()

        if self._is_accounting_contract_blocked(status):
            blocked_action_ids |= self._get_blocked_action_ids(
                INACTIVE_FREE_BLOCKED_MENUS
            )
            _logger.debug(
                "Accounting action guard: company_id=%s company=%s status=%s type=%s blocked_actions=%s",
                status.company_id.id,
                status.company_id.name,
                status.contract_status,
                status.contract_type,
                len(blocked_action_ids),
            )

        if self._is_certification_contract_blocked(status):
            blocked_action_ids |= self._get_blocked_action_ids(CERT_BLOCKED_MENUS)
            _logger.debug(
                "Certification action guard: company_id=%s company=%s status=%s type=%s blocked_actions=%s",
                status.company_id.id,
                status.company_id.name,
                status.contract_status,
                status.contract_type,
                len(blocked_action_ids),
            )

        blocked_actions = self.filtered(lambda action: action.id in blocked_action_ids)
        if blocked_actions:
            action_names = ", ".join(blocked_actions.mapped("name"))
            lang = self.env.user.lang or self.env.context.get("lang")
            if lang and lang.startswith("pt"):
                msg = (
                    f"Restrição de contrato: esta funcionalidade não está disponível "
                    f"enquanto o contrato estiver expirado ou não for encontrado ({action_names})."
                )
            else:
                msg = (
                    f"Contract restriction: this feature is unavailable while "
                    f"the contract is expired or not found ({action_names})."
                )
            raise AccessError(msg)

    def read(self, fields=None, load="_classic_read"):
        self._raise_if_contract_action_blocked()
        return super().read(fields=fields, load=load)

    def _get_action_dict(self):
        self._raise_if_contract_action_blocked()
        return super()._get_action_dict()
