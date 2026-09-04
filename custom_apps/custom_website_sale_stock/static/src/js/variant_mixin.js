/** @odoo-module **/

import VariantMixin from "@website_sale/js/sale_variant_mixin";
import publicWidget from "@web/legacy/js/public/public_widget";
import { renderToFragment } from "@web/core/utils/render";
import { formatFloat } from "@web/core/utils/numbers";
import { markup } from "@odoo/owl";

/**
 * Override to inject current lang into combination before rendering
 * so the QWeb template can switch text based on language.
 */
const originalOnChangeCombinationStock = VariantMixin._onChangeCombinationStock;

VariantMixin._onChangeCombinationStock = async function (ev, $parent, combination) {
    // Inject the current page language into combination context
    combination.current_lang = document.documentElement.lang || 'en';
    return originalOnChangeCombinationStock.apply(this, arguments);
};

export default VariantMixin;
