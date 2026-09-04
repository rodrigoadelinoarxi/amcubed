/** @odoo-module */

import {patch} from "@web/core/utils/patch";
import {PosStore} from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    //@override
    async processServerData() {
        await super.processServerData(...arguments);
        this['account_move_reasons'] = this.models["account.move.reason"].getAll();
        this['refund_type'] = this.models["tax.report.refund.type"].getAll();
    },
});
