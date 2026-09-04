/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AccountPaymentField } from "@account/components/account_payment_field/account_payment_field";

patch(AccountPaymentField.prototype, {
    onInfoClick(ev, line) {
        this.popover.open(ev.currentTarget, {
            title: _t("Journal Entry Info"),
            ...line,
            is_self_paid: this.props.record.data.is_self_paid || false,
            move_type: this.props.record.data.move_type || false,
            _onRemoveMoveReconcile: this.removeMoveReconcile.bind(this),
            _onOpenMove: this.openMove.bind(this),
        });
    },
});