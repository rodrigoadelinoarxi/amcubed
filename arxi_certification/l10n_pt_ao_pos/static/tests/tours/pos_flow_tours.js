/** POS flow tours for l10n_pt_ao_pos (Grupo 1 — POS).
 *
 * Functional end-to-end tours driven from the Python HttpCase in
 * tests/test_pos_flows.py. They exercise the certified PT/AO POS flows on top
 * of the merged satellites (default end consumer, invoicing journals, credit
 * note reason), reusing the native point_of_sale tour helpers so the steps stay
 * aligned with the standard POS UI.
 *
 * Product used: "Magnetic Board" (list_price 1.98, no to_weight), a core POS
 * fixture from TestPointOfSaleHttpCommon, so quantities and payment amounts are
 * deterministic.
 */
import { registry } from "@web/core/registry";
import { inLeftSide } from "@point_of_sale/../tests/pos/tours/utils/common";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Order from "@point_of_sale/../tests/generic_helpers/order_widget_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";

const PRODUCT = "Magnetic Board";
const PRICE = "1.98";

// Flow 1 — full cash sale: open register, add a product, pay cash, close order.
registry.category("web_tour.tours").add("l10n_pt_ao_pos_sale_flow", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct(PRODUCT, true, "1"),
            inLeftSide(Order.hasLine({ productName: PRODUCT })),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash", true, { amount: PRICE }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.orderIsEmpty(),
            ProductScreen.closePos(),
        ].flat(),
});

// Flow 2 — invoicing from POS: sale with a customer, tick Invoice, validate.
// Exercises _prepare_invoice_vals (invoicing journal routing) on a certified
// PT/AO order.
registry.category("web_tour.tours").add("l10n_pt_ao_pos_invoice_flow", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct(PRODUCT, true, "1"),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("AO Cert Customer"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            // PT/AO orders are already to_invoice (forced in models.js setup);
            // clicking the Invoice button here would toggle it OFF.
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.closePos(),
        ].flat(),
});

// Flow 3 — refund / credit note: pay an order, then refund it from the ticket
// screen and pay the refund. Covers the negative-amount credit-note path.
registry.category("web_tour.tours").add("l10n_pt_ao_pos_refund_flow", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // paid order to refund later
            ProductScreen.clickDisplayedProduct(PRODUCT, true, "1"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash", true, { amount: PRICE }),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.orderIsEmpty(),
            // refund it: open Orders, filter to the paid order, refund it
            Chrome.clickOrders(),
            TicketScreen.selectFilter("Paid"),
            TicketScreen.selectOrderByPrice(PRICE),
            TicketScreen.confirmRefund(),
            PaymentScreen.isShown(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            // credit-note reason popup (absorbed from
            // l10n_pt_ao_pos_credit_note_reason): default reason is "Other",
            // which requires a custom text before it can be confirmed.
            {
                trigger: ".popup .custom_value",
                run: "edit Devolução de teste",
            },
            {
                trigger: ".modal-footer .btn-primary:contains('Ok')",
                run: "click",
            },
            ReceiptScreen.isShown(),
            ReceiptScreen.clickNextOrder(),
            ProductScreen.closePos(),
        ].flat(),
});
