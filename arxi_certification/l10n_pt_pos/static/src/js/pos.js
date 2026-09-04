/** @odoo-module **/

    import { PosStore } from "@point_of_sale/app/services/pos_store";
    import { patch } from "@web/core/utils/patch";
    import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
    import { _t } from "@web/core/l10n/translation";

    patch(PosStore.prototype, {
        is_pt_country() {
            let countries = ['PT'];
            if (!this.company.country_id) {
                this.dialog.add(AlertDialog, {
                    title: _t("Missing Country"),
                    body: _t('The company %s doesn\'t have a country set.', this.company.name),
                });
                return false;
            }
            if (countries.includes(this.company.country_id.code)) {
                return true;
            }
            else{
                return false;
            }
        },
});
