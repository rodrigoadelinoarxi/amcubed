/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class ContractStatusBanner extends Component {
    static template = "contract_instance_checker.ContractStatusBanner";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        // This component is registered in the "main_components" registry,
        // so it mounts in every webclient env, not just the ones that have
        // gone through the full backend session bootstrap — "company" isn't
        // always there yet (reliably reproducible on a plain page reload).
        // useService("company") would throw synchronously in that case, so
        // this reads the service directly and simply skips company-change
        // tracking below when it's absent, instead of crashing the banner.
        this.company = this.env.services.company ?? null;
        this.state = useState({
            status: null,
            loading: true,
            validating: false,
        });

        onWillStart(async () => {
            await this.loadContractStatus();
        });

        onMounted(() => {
            // Reload status every 5 minutes
            this.intervalId = setInterval(() => {
                this.loadContractStatus();
            }, 5 * 60 * 1000);

            // Track company changes to reload status (only when the
            // "company" service is actually available — see setup()).
            if (this.company) {
                this._lastCompanyId = this.company.currentCompany?.id;
                this._checkCompanyInterval = setInterval(() => {
                    const currentCompanyId = this.company.currentCompany?.id;
                    if (this._lastCompanyId !== currentCompanyId) {
                        this._lastCompanyId = currentCompanyId;
                        this.loadContractStatus();
                    }
                }, 1000); // Check every second for company changes
            }
        });
    }

    willUnmount() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }
        if (this._checkCompanyInterval) {
            clearInterval(this._checkCompanyInterval);
        }
    }

    async loadContractStatus() {
        try {
            const result = await this.orm.call(
                "contract.instance.status",
                "get_latest_status_dict",
                []
            );
            this.state.status = result;
            this.state.loading = false;
        } catch (error) {
            console.error("Error loading contract status:", error);
            this.state.loading = false;
        }
    }

    get showUserInfo() {
        if (!this.state.status) return true;
        return this.state.status.show_user_info !== false;
    }

    get accountManagerEmail() {
        return this.state.status?.account_manager_email || 'sales@arxi.pt';
    }

    get accountManagerName() {
        return this.state.status?.account_manager_name || 'Account Manager';
    }

    get shouldShowBanner() {
        if (!this.state.status) return false;
        if (this.state.status.is_neutralized) return false;
        // Only show banner for PT or AO companies
        if (!this.state.status.is_pt_or_ao_company) return false;

        const status = this.state.status.contract_status;

        // Normal behavior for production databases
        return ['expired', 'blocked', 'error', 'not_found'].includes(status) ||
               (status === 'active' && this.state.status.days_until_expiration <= 30) ||
               (status === 'active' && this.showUserInfo && this.state.status.current_user_count > this.state.status.user_limit);
    }

    get shouldShowBlockModal() {
        if (!this.state.status) return false;
        if (this.state.status.is_neutralized) return false;
        const fullBlockTypes = ['flybyodoo', 'therabox'];
        const contractType = this.state.status.contract_type || '';
        if (!fullBlockTypes.includes(contractType)) return false;
        return this.state.status.is_instance_blocked === true;
    }

    get bannerClass() {
        if (!this.state.status) return '';
        const status = this.state.status.contract_status;

        // In neutralized databases, always show as warning (yellow)
        if (this.state.status.is_neutralized) {
            return 'alert-warning';
        }

        // Normal behavior for production databases
        if (['expired', 'blocked', 'not_found', 'error'].includes(status)) {
            return 'alert-danger';
        }
        if (status === 'active' &&
            (this.state.status.days_until_expiration <= 30 ||
             (this.showUserInfo && this.state.status.current_user_count > this.state.status.user_limit))) {
            return 'alert-warning';
        }
        return '';
    }

    get bannerIcon() {
        if (!this.state.status) return '';
        const status = this.state.status.contract_status;

        // In neutralized databases, always use warning icon
        if (this.state.status.is_neutralized) {
            return 'fa-exclamation-triangle';
        }

        // Normal behavior for production databases
        if (['expired', 'blocked', 'not_found', 'error'].includes(status)) {
            return 'fa-times-circle';
        }
        return 'fa-exclamation-triangle';
    }

    get bannerMessage() {
        if (!this.state.status) return '';
        const status = this.state.status.contract_status;
        const s = this.state.status;

        // Add [TEST MODE] prefix and warning for neutralized databases
        let message = '';
        const prefix = s.is_neutralized ? _t('[TEST MODE] ') : '';
        const neutralizedWarning = s.is_neutralized ? _t(' | WARNING: Generated hashes are NOT valid for SAF-T or tax purposes!') : '';

        if (status === 'not_found') {
            if (s.is_in_grace_period && s.grace_period_end) {
                const graceEnd = new Date(s.grace_period_end);
                const hoursLeft = Math.ceil((graceEnd - new Date()) / (1000 * 60 * 60));
                message = _t('CONTRACT NOT FOUND - Grace period: %s hours remaining. Resolve urgently!', hoursLeft);
            } else {
                message = _t('CONTRACT NOT FOUND - Grace period expired! Contact support immediately!');
            }
        } else if (status === 'blocked' || status === 'expired') {
            message = _t('ARXI CONTRACT BLOCKED/EXPIRED - Contact ARXI support immediately!');
        } else if (status === 'error') {
            message = _t('CONTRACT VALIDATION ERROR - Check your settings');
        } else if (status === 'active' && s.days_until_expiration <= 30) {
            message = _t('ARXI CONTRACT EXPIRES IN %s DAYS - Renew your contract', s.days_until_expiration);
        } else if (status === 'active' && this.showUserInfo && s.current_user_count > s.user_limit) {
            message = _t('USER LIMIT EXCEEDED (%s/%s) - Contact your account manager', s.current_user_count, s.user_limit);
        }

        return prefix + message + neutralizedWarning;
    }

    get blockModalMessage() {
        if (!this.state.status) return '';
        const status = this.state.status.contract_status;
        const s = this.state.status;

        if (status === 'expired') {
            const endDate = s.end_date ? new Date(s.end_date).toLocaleDateString() : _t('unknown date');
            return _t('Your ARXI contract expired on %s. System access is blocked until contract renewal.', endDate);
        }
        if (status === 'not_found') {
            if (s.grace_period_end) {
                const graceEnd = new Date(s.grace_period_end);
                return _t('No valid contract was found for this instance. The 48-hour grace period expired on %s. System access is blocked until this situation is resolved.', graceEnd.toLocaleString());
            }
            return _t('No valid contract was found for this instance. System access is blocked.');
        }
        if (status === 'blocked') {
            return _t('Your ARXI contract is blocked. System access is temporarily unavailable.');
        }
        return _t('System access is blocked due to contract status.');
    }

    get checkNowLabel() {
        return _t('Check now');
    }

    get contactAccountManagerLabel() {
        return _t('Contact Account Manager');
    }

    get accessBlockedLabel() {
        return _t('Access Blocked');
    }

    get contactManagerInfo() {
        return _t('Please contact the Account Manager to fix this situation.');
    }

    get checkContractNowLabel() {
        return _t('Check Contract Now');
    }

    async onValidateNow() {
        if (this.state.validating) {
            return; // Prevent multiple clicks
        }

        this.state.validating = true;

        try {
            this.notification.add(
                _t("Validating contract with central server..."),
                { type: "info" }
            );

            await this.orm.call(
                "contract.instance.status",
                "action_force_validation_from_ui",
                []
            );

            // Reload status after validation
            await this.loadContractStatus();

            this.notification.add(
                _t("Contract validation completed. Check updated status."),
                { type: "success" }
            );
        } catch (error) {
            console.error("Error validating contract:", error);
            this.notification.add(
                _t("Error validating contract. Try again."),
                { type: "danger" }
            );
        } finally {
            this.state.validating = false;
        }
    }
}

// Register the component as a main component to be mounted automatically
registry.category("main_components").add("ContractStatusBanner", {
    Component: ContractStatusBanner,
    props: {},
});
