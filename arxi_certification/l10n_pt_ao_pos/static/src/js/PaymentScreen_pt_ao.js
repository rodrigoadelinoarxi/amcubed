/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

// PT/AO PaymentScreen patch (absorbed from l10n_pt_ao_pos_document_type and
// l10n_pt_ao_pos_invoicing_journals). Two independent concerns kept side by side
// here: fiscal document type (FS/FT/FR/NC) and the invoicing journal.
// v19: get_order -> getOrder, get_total_with_tax -> amount_total,
// isRefund() -> isRefundDoc().
patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        const order = this.pos.getOrder();

        // Document type (from l10n_pt_ao_pos_document_type).
        if (order.isRefundDoc()) {
            order.set_document_type('NC');
        } else if (order.amount_total > 0 && order.amount_total < 100) {
            order.set_document_type('FS');
        } else if (order.amount_total > 0) {
            order.set_document_type('FR');
        } else {
            order.set_document_type('FR');
        }

        if (!order.is_pt_ao_country()) {
            order.set_document_type('FT');
        }

        // Invoicing journal (from l10n_pt_ao_pos_invoicing_journals). v19:
        // this.pos.journals is populated in invoicing_journals.js
        // (PosStore.processServerData); config.invoicing_journal_ids is loaded
        // via pos.config._load_pos_data_fields.
        const configJournalIds = (this.pos.config.invoicing_journal_ids || []).map(
            (j) => (typeof j === "object" ? j.id : j)
        );
        this.invoicing_journal_map = (this.pos.journals || []).filter((journal) =>
            configJournalIds.includes(journal.id)
        );
        if (order && this.invoicing_journal_map.length) {
            order.set_invoicing_journal_id(this.invoicing_journal_map[0].id);
        }
    },

    toggleSimplifiedInvoice() {
        if (this.currentOrder.isRefundDoc()) {
            return;
        }
        this.currentOrder.set_document_type('FS');
    },

    toggleNormalInvoice() {
        if (this.currentOrder.isRefundDoc()) {
            return;
        }
        this.currentOrder.set_document_type('FT');
    },

    toggleInvoiceReceipt() {
        if (this.currentOrder.isRefundDoc()) {
            return;
        }
        this.currentOrder.set_document_type('FR');
    },

    toggleJournalInvoice(journal) {
        const order = this.pos.getOrder();
        order.set_invoicing_journal_id(journal.id);
    },

    async validateOrder(isForceValidate) {
        const order = this.pos.getOrder();
        if (order.is_pt_ao_country()) {
            if (!order.invoicing_journal_id) {
                this.dialog.add(AlertDialog, {
                    title: _t("Empty Invoicing Journal"),
                    body: _t(
                        "There must be an Invoicing Journal in your order before it can be validated and invoiced."
                    ),
                });
                return false;
            }
        }
        await super.validateOrder(...arguments);
    },
});
