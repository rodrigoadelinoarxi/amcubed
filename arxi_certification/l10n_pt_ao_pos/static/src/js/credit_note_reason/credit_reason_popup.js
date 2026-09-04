/** @odoo-module */

import {_t} from "@web/core/l10n/translation";
import {usePos} from "@point_of_sale/app/hooks/pos_hook";
import { Component, useState, useEffect } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class CreditReasonPopup extends Component {
    static template = "l10n_pt_ao_pos_credit_note_reason.CreditReasonPopup";
    static components = { Dialog };
    static props = {
        confirmText: { type: String, optional: true },
        cancelText: { type: String, optional: true },
        title: { type: String, optional: true },
        order: Object,
        close: Function,
        getPayload: Function
    };

    setup() {
        super.setup();
        this.pos = usePos();
        const order = this.props.order;
        this.values = [...this.pos.account_move_reasons];
        this.refundTypes = [...this.pos.refund_type];
        this.refundTypeLabel = _t("Refund Type");
        this.values.push({
            'id': 'other',
            'name': _t('Other'),
        })
        this.state = useState({
            credit_reasons: this.values[0].id,
            refund_type: this.refundTypes[0]?.id || null,
            custom_value: "",
            is_custom: false,
            create_for_future_use: false
        });
        useEffect(
            () => {
                this.state.is_custom = this.state.create_for_future_use = this.state.credit_reasons === 'other';
            },
            () => [this.state.credit_reasons, this.state.refund_type],
        );
    }

    confirm() {
        let reason_text;
        if (this.state.is_custom) {
            if (!this.state.custom_value) {
                // If custom value is empty, show a message and return
                alert(_t("Custom value is required"));
                return;
            }
            reason_text = this.state.custom_value;
        } else {
            // Find the reason text from the values array
            const selectedReason = this.values.find(reason => String(reason.id) === String(this.state.credit_reasons));
            reason_text = selectedReason ? selectedReason.name : "";
        }
        this.state.reason_text = reason_text;
        this.props.getPayload(this.state);
        this.props.close();
    }

    onReasonChange(event) {
        this.state.credit_reasons = event.target.value;
    }
    onRefundTypeChange(event) {
        this.state.refund_type = event.target.value;
    }

}
