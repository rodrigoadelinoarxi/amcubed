/** @odoo-module **/

import { PartnerLine } from "@point_of_sale/app/screens/partner_list/partner_line/partner_line";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Block the pos_settle_due customer-due settlement paths for PT/AO companies.
 *
 * In PT/AO every POS transaction must go through the certified invoicing flow
 * (l10n_pt_ao_pos), so settling a customer's outstanding balance directly from
 * the customer screen — which does not issue a certified document — is not
 * allowed. The v18 module suppressed the "Settle Customer Due" DropdownItem with
 * an XPath on partner_line.xml, but v19 restructured pos_settle_due's template
 * (the actions now live in a shared CustomDropdownItems sub-template with
 * several items), so that XPath no longer matches and would break module load.
 *
 * We therefore guard the *methods* pos_settle_due patches onto PartnerLine
 * (settleCustomerDue / settleCustomerInvoices / depositMoney) instead of the
 * markup: independent of the template structure, and stable across minor
 * Enterprise changes. The block short-circuits with an explanatory dialog and
 * never calls the native settlement, so no un-certified movement is created.
 */
patch(PartnerLine.prototype, {
    _pt_ao_settle_blocked() {
        if (this.pos.is_pt_ao_country()) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Not allowed"),
                body: _t(
                    "Settling a customer's due directly is not allowed in Portugal/Angola: "
                    + "every point of sale transaction must be issued through the certified "
                    + "invoicing flow."
                ),
            });
            return true;
        }
        return false;
    },

    async settleCustomerDue() {
        if (this._pt_ao_settle_blocked()) {
            return;
        }
        return super.settleCustomerDue(...arguments);
    },

    async settleCustomerInvoices() {
        if (this._pt_ao_settle_blocked()) {
            return;
        }
        return super.settleCustomerInvoices(...arguments);
    },

    async depositMoney() {
        if (this._pt_ao_settle_blocked()) {
            return;
        }
        return super.depositMoney(...arguments);
    },
});
