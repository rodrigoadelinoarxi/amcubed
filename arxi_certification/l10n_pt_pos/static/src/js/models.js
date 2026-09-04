/** @odoo-module **/
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    setup() {
        super.setup(...arguments);
        // Certified receipt data (qr_code, pt_arxi_atcud, related hash) is
        // loaded onto the order by the v19 pos.order load-data channel and read
        // straight off it (props.order.*); the v18 _export_for_ui / the
        // export_for_printing dict are both gone, so no override is needed here.
        this.qr_code = this.qr_code || false;
        this.atcud = this.atcud || false;
        this.pt_arxi_atcud = this.pt_arxi_atcud || false;
        this.pt_arxi_inalterable_hash = this.pt_arxi_inalterable_hash || false;
    },
    set_qr_code(qr_code) {
        this.qr_code = qr_code;
    },
    get_qr_code() {
        return this.qr_code;
    },
    set_atcud(atcud) {
        this.atcud = atcud;
    },
    get_atcud() {
        return this.atcud;
    },
    get_qr_style() {
        return this.config_id.qr_style;
    },
    _get_qr_code_data() {
        if (this.is_pt_country()) {
            return this.qr_code;
        } else {
            return false;
        }
    },
});
