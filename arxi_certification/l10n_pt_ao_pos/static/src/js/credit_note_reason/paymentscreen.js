/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { CreditReasonPopup } from "./credit_reason_popup";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
    },

    async validateOrder(isForceValidate) {
        const order = this.pos.getOrder();
        const total = order.amount_total;

        // Check if any line has refunded_orderline_id
        const hasRefundedLines = order.lines && order.lines.some(line => line.refunded_orderline_id);

        // Check if this is a refund using the centralized method (with fallback)
        // Handle -0 case with Object.is
        const isRefund = order.isRefund ||
                        order.refunded_order_id ||
                        hasRefundedLines ||
                        total < 0 ||
                        Object.is(total, -0);

        if (isRefund) {
            const payload = await makeAwaitable(this.dialog, CreditReasonPopup, {
                order: order});

            if (!payload) {
                return false; // user cancelled
            }

            order.set_credit_reason_text(payload.reason_text);

            this.currentOrder.update({
            refund_type: parseInt(payload.refund_type),
            });

            if (payload.create_for_future_use) {
                try {
                    const new_id = await this.env.services.orm.call(
                        "account.move.reason",
                        "create",
                        [{
                            name: payload.reason_text,
                        }],
                    );

                    // Now fetch full data for that reason
                    const [new_reason] = await this.env.services.orm.call(
                        "account.move.reason",
                        "read",
                        [[new_id], ["id", "name"]]
                    );


                    // Push the complete record into your POS list
                    this.pos.account_move_reasons.push(new_reason);

                } catch (error) {
                    console.error("Failed to save refund reason:", error);
                }
            }
        }
        await super.validateOrder(isForceValidate);
    },
});
