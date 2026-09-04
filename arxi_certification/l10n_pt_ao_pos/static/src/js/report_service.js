/** @odoo-module */

import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { downloadReport } from "@web/webclient/actions/reports/utils";

// Get the existing reportService
const existingReportService = registry.category("services").get("report");

// Extend the reportService
const customReportService = {
    dependencies: ["ui", "orm"],
    start(env, { ui, orm }) {
        const reportActionsCache = {};

        // Get the original service if it exists
        let originalService = {};
        if (existingReportService && existingReportService.start) {
            originalService = existingReportService.start(env, { ui, orm });
        }

        return {
            ...originalService,
            async doAction(reportXmlId, active_ids) {
                // Check if this is the account invoices report that should be skipped
                if (reportXmlId === "account.account_invoices") {
                    // CUSTOM -> Ignore downloading this report as it is not certified
                    return false;
                }

                // Default behavior - use the imported rpc and user
                ui.block();
                try {
                    reportActionsCache[reportXmlId] ||= rpc("/web/action/load", {
                        action_id: reportXmlId,
                    });
                    const reportAction = await reportActionsCache[reportXmlId];
                    // await instead of return because we want the ui to stay blocked
                    await downloadReport(
                        rpc,
                        { ...reportAction, context: { active_ids } },
                        "pdf",
                        user.context
                    );
                } finally {
                    ui.unblock();
                }
            },
        };
    },
};

// Override existing service with our custom one
registry.category("services").add("report", customReportService, { force: true });
