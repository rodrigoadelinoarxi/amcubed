# -*- coding: utf-8 -*-

import requests
import logging
from datetime import date, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Contract types where user count/limit info is not relevant
NO_USER_INFO_TYPES = ("certification", "payroll", "accounting")

# Contract types that support full blocking (login denial + modal)
FULL_BLOCK_TYPES = ("flybyodoo", "therabox")


class ContractInstanceStatus(models.Model):
    """
    Model to store the status of the last contract validation.
    Serves as cache and history of validations.
    """

    _name = "contract.instance.status"
    _description = "Contract Instance Status"
    _order = "company_id, last_check_date desc"

    name = fields.Char(string="Name", default="Contract Status", readonly=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        help="Company for which this contract status applies",
    )

    # Last validation data
    last_check_date = fields.Datetime(
        string="Last Check Date",
        readonly=True,
        help="Date and time of last check with the central server",
    )

    contract_status = fields.Selection(
        [
            ("active", "Active"),
            ("expired", "Expired"),
            ("error", "Error"),
            ("not_found", "Not Found"),
        ],
        string="Contract Status",
        readonly=True,
        help="Contract status returned by the central server",
    )

    end_date = fields.Date(
        string="Contract End Date", readonly=True, help="Contract end date"
    )

    user_limit = fields.Integer(
        string="User Limit", readonly=True, help="Maximum number of allowed users"
    )

    current_user_count = fields.Integer(
        string="Current User Count",
        readonly=True,
        help="Number of active users at last check",
    )

    block_instance = fields.Boolean(
        string="Block Instance",
        readonly=True,
        default=False,
        help="Indicates if the instance should be blocked when contract expires",
    )

    grace_period_end = fields.Datetime(
        string="Grace Period End",
        readonly=True,
        help="Date and time when the grace period ends (48h after first problem detection)",
    )

    days_until_expiration = fields.Integer(
        string="Days Until Expiration",
        readonly=True,
        help="Days remaining until expiration",
    )

    error_message = fields.Text(
        string="Error Message",
        readonly=True,
        help="Error message from last validation (if any)",
    )

    # Additional contract information
    contract_name = fields.Char(string="Contract Name", readonly=True)

    contract_type = fields.Char(string="Contract Type", readonly=True)

    account_manager_name = fields.Char(string="Account Manager Name", readonly=True)

    account_manager_email = fields.Char(string="Account Manager Email", readonly=True)

    # Computed fields for alerts
    is_expiring_soon = fields.Boolean(
        string="Expiring Soon",
        compute="_compute_expiring_soon",
        help="Indicates if the contract is close to expiration (less than 30 days)",
    )

    is_user_limit_exceeded = fields.Boolean(
        string="User Limit Exceeded",
        compute="_compute_user_limit_exceeded",
        help="Indicates if the number of users exceeds the limit",
    )

    is_instance_blocked = fields.Boolean(
        string="Instance Blocked",
        compute="_compute_instance_blocked",
        help="Indicates if the instance is blocked",
    )

    is_in_grace_period = fields.Boolean(
        string="In Grace Period",
        compute="_compute_in_grace_period",
        help="Indicates if still within the 48h grace period",
    )

    @api.depends("grace_period_end")
    def _compute_in_grace_period(self):
        """Determines if still within the grace period"""
        now = fields.Datetime.now()
        for status in self:
            if status.grace_period_end:
                status.is_in_grace_period = status.grace_period_end > now
            else:
                status.is_in_grace_period = False

    @api.depends("end_date", "contract_status")
    def _compute_expiring_soon(self):
        """Determines if the contract is close to expiration"""
        for status in self:
            if status.contract_status == "active" and status.end_date:
                today = date.today()
                days_until = (status.end_date - today).days
                status.is_expiring_soon = 0 < days_until <= 30
            else:
                status.is_expiring_soon = False

    @api.depends("current_user_count", "user_limit")
    def _compute_user_limit_exceeded(self):
        """Determines if the user limit has been exceeded"""
        for status in self:
            status.is_user_limit_exceeded = (
                status.current_user_count > 0
                and status.user_limit > 0
                and status.current_user_count > status.user_limit
            )

    @api.depends("contract_status", "block_instance", "grace_period_end")
    def _compute_instance_blocked(self):
        """
        Determina se a instância deve estar bloqueada.

        Lógica:
        - 'active': nunca bloqueia
        - 'expired': bloqueia IMEDIATAMENTE se block_instance=True (sem período de graça)
        - 'not_found': aplica período de graça de 48h, depois bloqueia SEMPRE
        - 'error': não bloqueia
        """
        now = fields.Datetime.now()
        for status in self:
            if status.contract_status == "active":
                # Active contract never blocks
                status.is_instance_blocked = False

            elif status.contract_status == "expired":
                # Expired contract: blocks IMMEDIATELY if block_instance=True
                # Only full-block types (flybyodoo/therabox) actually block
                status.is_instance_blocked = (
                    status.block_instance and status.contract_type in FULL_BLOCK_TYPES
                )

            elif status.contract_status == "not_found":
                # Contract not found: apply 48h grace period
                # After grace period, only full-block types get blocked
                if status.grace_period_end and status.grace_period_end > now:
                    # Still within grace period, don't block
                    status.is_instance_blocked = False
                else:
                    # Grace period expired, block only full-block types
                    status.is_instance_blocked = (
                        status.contract_type in FULL_BLOCK_TYPES
                    )

            elif status.contract_status == "error":
                # Validation errors don't block (may be temporary)
                status.is_instance_blocked = False

            else:
                # Any other case doesn't block
                status.is_instance_blocked = False

    @api.model
    def get_latest_status(self, company=None):
        """
        Returns the latest validation status for a company.
        Used to display alerts in the interface.
        """
        if not company:
            company = self.env.company

        return self.search(
            [("company_id", "=", company.id)], limit=1, order="last_check_date desc"
        )

    @api.model
    def get_latest_status_dict(self):
        """
        Returns the latest validation status as a dictionary.
        Utilizado para o banner JavaScript.
        """
        latest_status = self.get_latest_status()
        if not latest_status:
            return None

        # Check if database is neutralized (never show banner in neutralized DBs)
        is_neutralized = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("database.is_neutralized", False)
        )

        # Check if current user's company is PT or AO
        current_company = self.env.company
        is_pt_or_ao_company = False
        if current_company.country_id:
            country_code = current_company.country_id.code
            is_pt_or_ao_company = country_code in ("PT", "AO")

        effective_contract_type = (
            current_company.contract_type or latest_status.contract_type
        )
        show_user_info = effective_contract_type not in NO_USER_INFO_TYPES
        _logger.info(
            "get_latest_status_dict: company=%s, company.contract_type=%r, "
            "status.contract_type=%r, effective=%r, show_user_info=%s",
            current_company.name,
            current_company.contract_type,
            latest_status.contract_type,
            effective_contract_type,
            show_user_info,
        )

        return {
            "contract_status": latest_status.contract_status,
            "last_check_date": latest_status.last_check_date.isoformat()
            if latest_status.last_check_date
            else None,
            "end_date": latest_status.end_date.isoformat()
            if latest_status.end_date
            else None,
            "user_limit": latest_status.user_limit,
            "current_user_count": latest_status.current_user_count,
            "days_until_expiration": latest_status.days_until_expiration,
            "block_instance": latest_status.block_instance,
            "is_expiring_soon": latest_status.is_expiring_soon,
            "is_user_limit_exceeded": latest_status.is_user_limit_exceeded,
            "is_instance_blocked": latest_status.is_instance_blocked,
            "is_in_grace_period": latest_status.is_in_grace_period,
            "grace_period_end": latest_status.grace_period_end.isoformat()
            if latest_status.grace_period_end
            else None,
            "error_message": latest_status.error_message,
            "contract_name": latest_status.contract_name,
            "contract_type": effective_contract_type,
            "show_user_info": show_user_info,
            "is_pt_or_ao_company": is_pt_or_ao_company,
            "is_neutralized": is_neutralized,
            "account_manager_name": latest_status.account_manager_name or "",
            "account_manager_email": latest_status.account_manager_email or "",
        }

    @api.model
    def _cron_validate_contract(self):
        """
        Cron job that validates the contract with the central server.
        Runs daily and updates the contract status for all PT/AO companies.
        """
        # Validate contract for each company that has contract configuration
        # Filter by contract_token presence to only validate companies with contract setup
        companies = self.env["res.company"].search([("contract_token", "!=", False)])

        # Further filter to PT/AO companies
        pt_ao_companies = companies.filtered(
            lambda c: c.country_id and c.country_id.code in ("PT", "AO")
        )

        for company in pt_ao_companies:
            self._validate_contract_for_company(company)

    def _validate_contract_for_company(self, company):
        """
        Validates the contract for a specific company.
        """
        # Get company configurations
        nif = (company.contract_nif or "").strip()
        token = (company.contract_token or "").strip()
        central_server_url = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("contract_instance_checker.central_server_url")
        )

        if not nif or not token or not central_server_url:
            _logger.warning(
                f"Contract validation skipped for company {company.name}: Missing configuration (NIF, Token, or URL)"
            )
            self._create_status_record(
                company_id=company.id,
                contract_status="error",
                error_message="Configuration incomplete: Missing NIF, Token, or Central Server URL",
            )
            return

        # Count active internal users (not system, not portal)
        user_count = self.env["res.users"].search_count(
            [
                ("share", "=", False),
                ("active", "=", True),
                ("id", "!=", self.env.ref("base.user_admin").id),  # Excluir admin
            ]
        )

        # Preparar endpoint
        if not central_server_url.endswith("/"):
            central_server_url += "/"
        api_url = f"{central_server_url}api/contract/check"

        # Make request to central server
        try:
            _logger.info(f"Validating contract with central server: {api_url}")

            response = requests.get(
                api_url,
                params={
                    "nif": nif,
                    "token": token,
                    "user_count": user_count,
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()

                # Map contract status received from API
                api_status = data.get("status", "active")

                # Map contract states to instance_checker states
                if api_status == "blocked":
                    # Contract blocked on central server
                    contract_status = "expired"  # Tratamos como expirado
                elif api_status == "expired":
                    # Contrato expirado
                    contract_status = "expired"
                else:
                    # Contrato ativo
                    contract_status = "active"

                # Criar registo de status
                # IMPORTANT: block_instance comes from the contract on the central server
                # Se False, a instância não deve ser bloqueada mesmo que expire
                self._create_status_record(
                    company_id=company.id,
                    contract_status=contract_status,
                    end_date=data.get("end_date"),
                    user_limit=data.get("user_limit", 0),
                    current_user_count=user_count,
                    block_instance=data.get(
                        "block_instance", False
                    ),  # Default False se não especificado
                    days_until_expiration=data.get("days_until_expiration", 0),
                    contract_name=data.get("contract_name", ""),
                    contract_type=data.get("contract_type", ""),
                    account_manager_name=data.get("account_manager_name", ""),
                    account_manager_email=data.get("account_manager_email", ""),
                )

                # Persist contract_type on the company for reliable show_user_info
                api_contract_type = data.get("contract_type", "")
                if api_contract_type:
                    company.sudo().write({"contract_type": api_contract_type})
                    _logger.info(
                        'Contract type "%s" persisted to company %s (id=%d)',
                        api_contract_type,
                        company.name,
                        company.id,
                    )

                _logger.info(
                    f"Contract validated successfully: Status={api_status} -> {contract_status}, "
                    f"End Date={data.get('end_date')}, Users={user_count}/{data.get('user_limit')}, "
                    f"Block Instance={data.get('block_instance')}, "
                    f"Contract Type={api_contract_type}, "
                    f"Show User Info={api_contract_type not in NO_USER_INFO_TYPES}"
                )

            elif response.status_code == 404:
                error_data = response.json()
                error_msg = error_data.get("error", "Contract not found")

                # Verificar se já existe um status 'not_found' anterior para esta empresa
                previous_not_found = self.search(
                    [
                        ("company_id", "=", company.id),
                        ("contract_status", "=", "not_found"),
                        ("grace_period_end", "!=", False),
                    ],
                    order="last_check_date desc",
                    limit=1,
                )

                # Se já existe um período de graça ativo, manter o mesmo
                if (
                    previous_not_found
                    and previous_not_found.grace_period_end > fields.Datetime.now()
                ):
                    grace_period_end = previous_not_found.grace_period_end
                    _logger.warning(
                        f"Contract not found for {company.name}: Continuing grace period until {grace_period_end}"
                    )
                else:
                    # Criar novo período de graça de 48 horas
                    grace_period_end = fields.Datetime.now() + timedelta(hours=48)
                    _logger.warning(
                        f"Contract not found for {company.name}: Starting 48h grace period until {grace_period_end}"
                    )

                self._create_status_record(
                    company_id=company.id,
                    contract_status="not_found",
                    error_message=error_msg,
                    current_user_count=user_count,
                    block_instance=False,  # Não usado para 'not_found', usa grace_period_end
                    grace_period_end=grace_period_end,
                )

                _logger.error(f"Contract not found: {error_msg}")

            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                self._create_status_record(
                    company_id=company.id,
                    contract_status="error",
                    error_message=error_msg,
                    current_user_count=user_count,
                )
                _logger.error(
                    f"Contract validation failed for {company.name}: {error_msg}"
                )

        except requests.exceptions.Timeout:
            error_msg = "Connection timeout to central server"
            self._create_status_record(
                company_id=company.id,
                contract_status="error",
                error_message=error_msg,
                current_user_count=user_count,
            )
            _logger.error(f"Contract validation failed for {company.name}: {error_msg}")

        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            self._create_status_record(
                company_id=company.id,
                contract_status="error",
                error_message=error_msg,
                current_user_count=user_count,
            )
            _logger.error(f"Contract validation failed for {company.name}: {error_msg}")

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._create_status_record(
                company_id=company.id,
                contract_status="error",
                error_message=error_msg,
                current_user_count=user_count,
            )
            _logger.error(
                f"Contract validation failed for {company.name}: {error_msg}",
                exc_info=True,
            )

    def _create_status_record(self, **values):
        """Helper para criar registo de status"""
        values["last_check_date"] = fields.Datetime.now()
        record = self.create(values)
        # Clear caches so contract restrictions use latest status immediately.
        self.env.registry.clear_cache()
        return record

    @api.model
    def check_instance_blocked(self):
        """
        Verifica se a instância está bloqueada.
        Utilizado no hook de autenticação.
        """
        # Never block on neutralized/staging databases
        is_neutralized = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("database.is_neutralized", False)
        )
        if is_neutralized:
            return False

        latest_status = self.get_latest_status()

        if not latest_status:
            # If no status, allow access (first installation)
            return False

        # Block if contract expired or not found and block_instance=True
        if latest_status.is_instance_blocked:
            _logger.warning(
                f"Instance blocked: Contract status={latest_status.contract_status}, "
                f"Block instance={latest_status.block_instance}"
            )
            return True

        return False

    @api.model
    def _check_certification_contract(self, records):
        is_neutralized = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("database.is_neutralized", False)
        )
        if is_neutralized:
            return

        companies = records.mapped("company_id")
        for company in companies:
            status = self.get_latest_status(company)
            if not status:
                continue
            if status.contract_type == "certification" and status.contract_status in (
                "expired",
                "not_found",
            ):
                lang = self.env.user.lang or self.env.context.get("lang")
                is_pt = lang and lang.startswith("pt")
                status_label = (
                    {"expired": "expirado", "not_found": "não encontrado"}
                    if is_pt
                    else {"expired": "expired", "not_found": "not found"}
                ).get(status.contract_status, status.contract_status)
                if is_pt:
                    msg = (
                        f"Não pode executar esta ação porque o contrato de certificação "
                        f"da empresa {company.name} está {status_label}. "
                        "Contacte o seu gestor de conta."
                    )
                else:
                    msg = (
                        f"You cannot perform this action because the certification contract "
                        f"for company {company.name} is {status_label}. "
                        "Contact your account manager."
                    )
                raise UserError(msg)

    @api.model
    def get_block_message(self):
        """Returns block message to display to the user"""
        latest_status = self.get_latest_status()

        if not latest_status:
            return _("Unable to validate contract. Please contact support.")

        manager_name = latest_status.account_manager_name or _("ARXI Support")
        manager_email = latest_status.account_manager_email or "sales@arxi.pt"
        contact_info = _(
            "Please contact %(name)s (%(email)s).",
            name=manager_name,
            email=manager_email,
        )

        if latest_status.contract_status == "expired":
            end_date_str = (
                latest_status.end_date.strftime("%Y-%m-%d")
                if latest_status.end_date
                else _("unknown date")
            )
            return (
                _(
                    "Your FlyByOdoo contract has expired on %(date)s. ",
                    date=end_date_str,
                )
                + contact_info
            )
        elif latest_status.contract_status == "not_found":
            return _("No valid contract found for this instance. ") + contact_info
        elif latest_status.contract_status == "error":
            return (
                _(
                    "Unable to validate contract: %(error)s. ",
                    error=latest_status.error_message or _("Unknown error"),
                )
                + contact_info
            )
        else:
            return _("Instance access blocked. ") + contact_info

    def action_force_validation(self):
        """Manual action to force immediate validation (used in form buttons)"""
        self._cron_validate_contract()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Contract Validation",
                "message": "Contract validation completed. Check the latest status.",
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def action_force_validation_from_ui(self):
        """
        Method called by JavaScript banner to validate contract.
        Returns True to indicate success (JS will reload status).
        """
        _logger.info("Manual contract validation triggered from UI")
        self._validate_contract_for_company(self.env.company)
        return True
