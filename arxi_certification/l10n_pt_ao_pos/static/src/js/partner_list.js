/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";


patch(PartnerList.prototype,  {
    async getNewPartners() {
        let domain = [];
        const limit = 30;
        if (this.state.query) {
            const search_fields = ["name", "vat", "parent_name", "phone_mobile_search", "email", "barcode"];
            domain = [
                ...Array(search_fields.length - 1).fill('|'),
                ...search_fields.map(field => [field, "ilike", this.state.query + "%"])
            ];
        }
        // FIXME POSREF timeout
        const result = await this.pos.data.searchRead("res.partner", domain, [], {
            limit: limit,
            offset: this.state.currentOffset,
        });
        return result;
    }
});
