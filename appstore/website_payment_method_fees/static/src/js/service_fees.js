/** @odoo-module */

import publicWidget from '@web/legacy/js/public/public_widget';
import '@website_sale/js/website_sale_delivery';

// Utility function to update totals
function updateTotalWithFees(methodFees, currencySymbol) {
    const totalElement = document.querySelector('[data-total-fees]');
    const feesPercentageElement = document.querySelector('.method_fees_percentage');
    const OrdertotalElement = document.querySelector('[data-totals]');

    if (totalElement) {
        // const totalAmount = parseFloat(document.querySelector('.monetary_field').textContent.replace(/[^0-9.-]+/g, ''));
        const text = document.querySelector('.monetary_field').textContent;
        // Try to detect the locale format and parse accordingly
        const cleanNumber = text.replace(/[^\d.,+-]/g, '');

        // Assume last separator is decimal if there are multiple
        const lastComma = cleanNumber.lastIndexOf(',');
        const lastDot = cleanNumber.lastIndexOf('.');

        let totalAmount;
        if (lastComma > lastDot) {
          // Comma is decimal separator (European format)
          totalAmount = parseFloat(cleanNumber.replace(/\./g, '').replace(',', '.'));
        } else {
          // Dot is decimal separator (US format)
          totalAmount = parseFloat(cleanNumber.replace(/,/g, ''));
        }
        const totalFees = totalAmount * (methodFees / 100);
        const totalWithFees = totalAmount + totalFees;

        totalElement.textContent = '';
        OrdertotalElement.textContent = '';

        totalElement.textContent = `${currencySymbol} ${totalFees.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (OrdertotalElement) {
            OrdertotalElement.innerHTML = `<strong>${currencySymbol} ${totalWithFees.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>`;
        }
        if (feesPercentageElement) {
            feesPercentageElement.textContent = `(${methodFees.toFixed(2)}%)`;
        }
    }
}


publicWidget.registry.PaymentForm.include({

    start: function () {
        const result = this._super(...arguments);

        const checkedRadio = document.querySelector('input[name="o_payment_radio"]:checked');
        if (checkedRadio) {
            let methodFees = parseFloat(checkedRadio.dataset.fees);
            if (isNaN(methodFees)) {
                methodFees = 0;
            }
            this._fetchCurrencySymbolAndUpdateTotal(methodFees);
        }
        return result;
    },

    async _selectPaymentOption(ev) {
        this._super(...arguments);

        let methodFees = parseFloat(ev.currentTarget.dataset.fees);
        if (isNaN(methodFees)) {
            methodFees = 0;
        }

        this._fetchCurrencySymbolAndUpdateTotal(methodFees);
    },

    async _fetchCurrencySymbolAndUpdateTotal(methodFees) {
        const amountHtml = this.paymentContext.currencyId;

        const currencyData = await this.orm.read('res.currency', [parseFloat(amountHtml)], ["symbol"]);
        const currencySymbol = currencyData && currencyData[0] ? currencyData[0].symbol : '';

        updateTotalWithFees(methodFees, currencySymbol);
    }

});

publicWidget.registry.websiteSaleDelivery.include({

    init() {
        this._super(...arguments);
        this.rpc = this.bindService("rpc");
        this.orm = this.bindService("orm");
    },

    async _onCarrierClick(ev) {
       await this._super(...arguments);

        setTimeout(async () => {
            const checkedRadio = document.querySelector('input[name="o_payment_radio"]:checked');
            if (checkedRadio) {
                let methodFees = parseFloat(checkedRadio.dataset.fees);
                if (isNaN(methodFees)) {
                    methodFees = 0;
                }

                const websiteId = (await this.orm.call('website', 'get_current_website')).match(/\d+/)[0];
                 const websiteInfo = await this.orm.read('website', [parseFloat(websiteId)], ["pricelist_id"]);
                const pricelistId = websiteInfo[0] ? websiteInfo[0].pricelist_id[0] : null;
                if (pricelistId){

                        const pricelistData = await this.orm.read('product.pricelist', [pricelistId], ["currency_id"]);
                        const currencyId = pricelistData[0] ? pricelistData[0].currency_id[0] : null;

                        if (currencyId) {
                            const currencyData = await this.orm.read('res.currency', [currencyId], ["symbol"]);
                            const currencySymbol = currencyData && currencyData[0] ? currencyData[0].symbol : '';

                            updateTotalWithFees(methodFees, currencySymbol);
                    }
                    }
            }
        }, 100);
    },

});
