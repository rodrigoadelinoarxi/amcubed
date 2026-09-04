/** @odoo-module **/
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PosOrder.prototype, {
    setup() {
        super.setup(...arguments);
        this.to_invoice = true;
        this.inalterable_hash = this.inalterable_hash || false;
        this.account_move_name = this.account_move_name || false;
        this.document_name = this.document_name || false;
        this.credit_reason = this.credit_reason || false;
        this.reversed_entry_name = this.reversed_entry_name || false;
        this.cashier_name = this.cashier_name || false;
        this.customer_name = this.customer_name || false;
        this.customer_vat = this.customer_vat || false;
        this.account_move_state = this.account_move_state || false;
        this.doc_printed = this.doc_printed || false;
        this.document_type = this.document_type || false;
    },

    // Document type FS/FT/FR/NC (absorbed from l10n_pt_ao_pos_document_type).
    set_document_type(document_type) { this.document_type = document_type; },
    get_document_type() { return this.document_type; },
    isSimplifiedInvoice() { return this.document_type === 'FS'; },
    isNormalInvoice() { return this.document_type === 'FT'; },
    isInvoiceReceipt() { return this.document_type === 'FR'; },

    // v19: the native `isRefund` is now a getter (is_refund === true); the old
    // v18 satellite defined an isRefund() *method* which shadowed it and made
    // every order look like a refund. Renamed here to avoid the collision while
    // keeping the certification refund-detection logic (amount / refunded lines).
    isRefundDoc() {
        const total = this.amount_total;
        const isNegativeTotal = total < 0 || Object.is(total, -0);
        const hasRefundedLines = this.lines && this.lines.some(line => line.refunded_orderline_id);
        return this.refunded_order_id || hasRefundedLines || isNegativeTotal;
    },

    // UAT POS/contabilidade, ponto 3 (Matías, 2026-08-28): "Imprimi uma
    // Fatura-Recibo e no talão vem impresso com Fatura" — OrderReceipt.xml
    // printed the literal, generic "Invoice n." label for every
    // non-refund document, regardless of the actual document_type
    // (FT/FS/FR). Gives the receipt the real, distinct label for each
    // type instead.
    getDocumentTypeLabel() {
        if (this.isInvoiceReceipt()) {
            return _t("Invoice-Receipt");
        }
        if (this.isSimplifiedInvoice()) {
            return _t("Simplified Invoice");
        }
        return _t("Invoice");
    },

    is_pt_ao_country() {
        if (['PT', 'AO'].includes(this.company_id.country_id.code)) {
            return true;
        } else {
            return false;
        }
    },

    // v19: PosOrder.setToInvoice replaces set_to_invoice
    setToInvoice(to_invoice) {
        if (this.is_pt_ao_country()) {
            this.assertEditable();
            this.to_invoice = true;
        } else {
            super.setToInvoice(...arguments);
        }
    },

    get_customer_vat(receipt) {
        if (this.company_id.country_id.code === 'PT' && (this.customer_vat === '999999990' || !this.customer_vat)) {
            return '---------'
        }
        if (this.company_id.country_id.code === 'AO' && this.customer_vat === '999999999' || !this.customer_vat) {
            return '---------'
        }
        return this.partner_id.vat
    },

    // Simple getters and setters
    set_inalterable_hash(inalterable_hash) { this.inalterable_hash = inalterable_hash; },
    get_inalterable_hash() { return this.inalterable_hash; },
    set_reversed_entry_name(reversed_entry_name) { this.reversed_entry_name = reversed_entry_name; },
    get_reversed_entry_name() { return this.reversed_entry_name; },
    set_credit_reason(credit_reason) { this.credit_reason = credit_reason; },
    get_credit_reason() { return this.credit_reason; },
    set_account_move_name(account_move_name) { this.account_move_name = account_move_name; },
    get_account_move_name() { return this.account_move_name; },
    set_document_name(document_name) { this.document_name = document_name; },
    get_document_name() { return this.document_name; },
    set_account_move_state(account_move_state) { this.account_move_state = account_move_state; },
    get_account_move_state() { return this.account_move_state; },
    set_cashier_name(cashier_name) { this.cashier_name = cashier_name; },
    get_cashier_name() { return this.cashier_name; },
    set_customer_name(customer_name) { this.customer_name = customer_name; },
    get_customer_name() { return this.customer_name; },
    set_customer_vat(customer_vat) { this.customer_vat = customer_vat; },

    // v19: PosOrder.waitForPushOrder replaces wait_for_push_order
    waitForPushOrder() {
        var result = super.waitForPushOrder(...arguments);
        result = Boolean(result || this.is_pt_ao_country());
        return result;
    },

    // v19: OrderReceipt reads certified fields straight off the order (no more
    // export_for_printing dict). The parsed exemption codes are exposed via a
    // getter the receipt template can read.
    get exemptionCodesForReceipt() {
        if (!this.exemption_codes) {
            return {};
        }
        try {
            if (typeof this.exemption_codes === 'string') {
                return JSON.parse(this.exemption_codes);
            }
            return this.exemption_codes;
        } catch (error) {
            console.error('Error parsing exemption codes:', error);
            return {};
        }
    },

    // v19: export_as_JSON was renamed serializeForORM
    serializeForORM(opts = {}) {
        const json = super.serializeForORM(...arguments);
        json.doc_printed = this.doc_printed || false;
        return json;
    },
});
