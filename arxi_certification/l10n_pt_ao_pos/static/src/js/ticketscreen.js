/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {TicketScreen} from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import {patch} from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    //@override
    _getSearchFields() {
        return Object.assign({}, {
            DOCUMENT_NUMBER: {
                repr: (order) => order.account_move_name,
                displayName: _t("Document Number"),
                modelField: "account_move_name",
            },
            VAT: {
                repr: (order) => order.customer_vat,
                displayName: _t("Customer VAT"),
                modelField: "customer_vat",
            },
        }, super._getSearchFields(...arguments));
    },
});
