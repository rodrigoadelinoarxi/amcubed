/** @odoo-module */
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosOrder.prototype, {
    setup() {
        super.setup(...arguments);
        this.invoicing_journal_id = this.invoicing_journal_id || false;
    },

    set_invoicing_journal_id(invoicing_journal_id) {
        this.invoicing_journal_id = invoicing_journal_id;
    },

    // v19: invoicing_journal_id is a Many2one, so it can be either a related
    // record (loaded from the server) or a plain id (set on click). Normalize
    // to the numeric id for the highlight comparison.
    getInvoicingJournalId() {
        const j = this.invoicing_journal_id;
        return j && typeof j === "object" ? j.id : j;
    },

    isSelectedJournal(journal) {
        return this.getInvoicingJournalId() === journal.id;
    },
});

patch(PosStore.prototype, {
    // @Override
    async processServerData() {
        await super.processServerData();
        this.journals = this.models["account.journal"].getAll();
    },
});
