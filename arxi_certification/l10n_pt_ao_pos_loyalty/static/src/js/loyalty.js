/** @odoo-module */
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(ProductScreen.prototype, {
    async addProductToOrder(product) {
        if (product.pos_loyalty_program) {
            this.dialog.add(AlertDialog, {
                title: _t("Pos Error"),
                body: _t("You cannot add Loyalty program products"),
            });
            return;
        }
        return super.addProductToOrder(...arguments);
    },
});

// The PT/AO core validation (l10n_pt_ao_pos) rejects any order with a product
// that has no taxes ("Some products do not have taxes configured"). A loyalty
// reward line intentionally carries no tax (the reward product must never add
// VAT — enforced in product.py), so without this the core would block every
// sale that has a reward. We run the core validation against a view of the
// order that excludes reward lines, so genuinely untaxed products are still
// caught while reward lines are exempt.
patch(OrderPaymentValidation.prototype, {
    async isOrderValid(isForceValidate) {
        const order = this.order;
        const originalGetOrderlines = order.getOrderlines.bind(order);
        const hasReward = originalGetOrderlines().some((line) => line.is_reward_line);
        if (!hasReward) {
            return super.isOrderValid(...arguments);
        }
        order.getOrderlines = () =>
            originalGetOrderlines().filter((line) => !line.is_reward_line);
        try {
            return await super.isOrderValid(...arguments);
        } finally {
            order.getOrderlines = originalGetOrderlines;
        }
    },
});
