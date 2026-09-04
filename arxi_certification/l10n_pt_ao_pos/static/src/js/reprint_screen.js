/** @odoo-module */

import {ReceiptScreen} from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

import {patch} from "@web/core/utils/patch";
import {useRef} from "@odoo/owl";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
    },


    async printDuplicateReceipt() {
        const order = this.currentOrder;
        // v19: OrderReceipt takes the order (not an export_for_printing dict);
        // the duplicate/triplicate label reads props.order.is_duplicated_print.
        // Do not force/persist doc_printed for manual duplicate prints; policy
        // is controlled by standard prints only.
        order.is_duplicated_print = true;
        order.is_triplicate_print = false;
        try {
            await this.env.services.printer.print(
                OrderReceipt,
                { order },
                { webPrintFallback: true }
            );
        } finally {
            order.is_duplicated_print = false;
        }
    },

    async printTriplicateReceipt() {
        const order = this.currentOrder;
        order.is_triplicate_print = true;
        order.is_duplicated_print = false;
        try {
            await this.env.services.printer.print(
                OrderReceipt,
                { order },
                { webPrintFallback: true }
            );
        } finally {
            order.is_triplicate_print = false;
        }
    },

});
