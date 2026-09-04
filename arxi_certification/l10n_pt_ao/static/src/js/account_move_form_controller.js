/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        // Check if this is action_post on account.move
        if (this.props.resModel === 'account.move' &&
            clickParams.name === 'action_post' &&
            clickParams.type === 'object') {

            // Create loading overlay
            const overlay = document.createElement('div');
            overlay.id = 'posting-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
            `;

            overlay.innerHTML = `
                <div style="background: white; padding: 30px; border-radius: 8px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <div class="spinner-border text-primary" style="width: 3rem; height: 3rem;" role="status">
                    </div>
                    <div style="margin-top: 15px; font-size: 16px; color: #333;">${_t("Posting document... Please wait.")}</div>
                    <div style="margin-top: 10px; font-size: 14px; color: #666;">${_t("Do not close this window.")}</div>
                </div>
            `;

            document.body.appendChild(overlay);

            // Store overlay reference for cleanup
            this._postingOverlay = overlay;
        }

        // Call the original method
        try {
            const res = await super.beforeExecuteActionButton(clickParams);
            // If the super call returns false (e.g., form invalid / required field
            // missing), the action won't execute and `afterExecuteActionButton`
            // will not be called. Ensure the overlay is removed in that case.
            if (res === false) {
                this._removePostingOverlay();
            }
            return res;
        } catch (error) {
            // Remove overlay on error
            this._removePostingOverlay();
            throw error;
        }
    },

    async afterExecuteActionButton(clickParams) {
        // Remove overlay after action completes
        this._removePostingOverlay();

        // Call the original method
        return super.afterExecuteActionButton(clickParams);
    },

    _removePostingOverlay() {
        if (this._postingOverlay) {
            try {
                document.body.removeChild(this._postingOverlay);
            } catch (e) {
                // Overlay might already be removed
            }
            this._postingOverlay = null;
        }
    }
});