/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    setup() {
        super.setup(...arguments);
        this.credit_reason_text = this.credit_reason_text || false;
        this.refund_type = this.refund_type || false;
    },

    set_credit_reason_text(credit_reason_text) {
        this.credit_reason_text = credit_reason_text;
    },

    get_credit_reason_text() {
        return this.credit_reason_text;
    },

    set_refund_type(refund_type) {
        this.refund_type = refund_type;
    },

    get_refund_type() {
        return this.refund_type;
    },
    // v19: the receipt reads order.credit_reason_text directly (set in setup),
    // so the old export_for_printing dict injection is no longer needed.
});
