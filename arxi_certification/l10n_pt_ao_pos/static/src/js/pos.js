/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    is_pt_ao_country() {
        let countries = ['PT', 'AO'];
        if (!this.company.country_id) {
            this.dialog.add(AlertDialog, {
                title: _t("Missing Country"),
                body: _t('The company %s doesn\'t have a country set.', this.company.name),
            });
            return false;
        }
        if (countries.includes(this.company.country_id.code)) {
            return true;
        }
        else{
            return false;
        }

    },
    // Standard receipt: from the 2nd print onward, mark doc_printed before printing
    async printReceipt() {
        try {
            const arg0 = arguments[0] || {};
            const order = arg0.order || this.getOrder();
            const priorPrints = order?.nb_print || 0; // nb_print reflects previous prints before calling super
            if (order && !order.doc_printed && priorPrints >= 1) {
                // Ensure "Copy" label on second and subsequent standard prints
                order.doc_printed = true;
            }
        } catch (_) {}

        const result = await super.printReceipt(...arguments);

        try {
            const arg0 = arguments[0] || {};
            const order = arg0.order || this.getOrder();
            if (order?.doc_printed && typeof order.id === "number") {
                await this.data.write("pos.order", [order.id], { doc_printed: true });
            }
        } catch (_) {}

        return result;
    },

});
