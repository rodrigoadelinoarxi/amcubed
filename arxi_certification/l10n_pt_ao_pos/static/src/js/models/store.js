import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async addLineToCurrentOrder(vals, opt = {}, configure = true) {
        const order = this.getOrder();
        if (order && !order.partner_id) {
            const configured = this.config.end_consumer_partner_id;
            // v19: setPartner expects a res.partner *record*, not an id. The
            // config field may reach the client as a record or as a raw id,
            // so resolve it against the loaded res.partner models when needed.
            let partner = configured;
            if (partner && typeof partner === "number") {
                partner = this.models["res.partner"].get(partner);
            }
            if (partner) {
                order.setPartner(partner);
            }
        }
        return await super.addLineToCurrentOrder(vals, opt, configure);
    }
});
