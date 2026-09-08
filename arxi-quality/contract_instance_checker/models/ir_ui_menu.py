# -*- coding: utf-8 -*-

# Menus to block when accounting contract is expired/not_found
# Uses env.ref with raise_if_not_found=False so missing modules are safe
INACTIVE_FREE_BLOCKED_MENUS = [
    # Recursos (Assets)
    "base_accounting_kit.menu_action_account_asset_asset_form",
    "account_asset.menu_action_account_asset_form",
    # Balancetes Portugueses (Portuguese Ledgers)
    "l10n_pt_reports_arxi.menu_action_account_report_analytic",
    # Rendimentos e Retenções — Residentes
    "l10n_pt_reports_arxi.menu_action_model_10",
    # Demonstração das Alterações no Capital Próprio
    "l10n_pt_reports_arxi.menu_statement_of_changes_in_equity_action",
    # COPE
    "l10n_pt_reports_arxi.menu_action_cope_report",
    # Modelo 30 - Rendimentos de Não Residentes
    "l10n_pt_reports_arxi.menu_action_model_30",
    # Balanço (Balance Sheet)
    "account_reports.menu_action_account_report_balance_sheet",
    # Ganhos e Perdas (Profit & Loss)
    "account_reports.menu_action_account_report_profit_and_loss",
    # Extrato de Fluxos de Caixa (Cash Flow Statement)
    "account_reports.menu_action_account_report_cash_flow",
    # Declaração de imposto (Tax Return)
    "account_reports.menu_action_account_report_gt",
    # EC Sales List
    "account_reports.menu_action_account_report_sales",
    # Diferimento (Deferred Expense)
    "account_reports.menu_action_account_report_deferred_expense",
    # Acréscimo (Deferred Revenue)
    "account_reports.menu_action_account_report_deferred_revenue",
    # Calendário de Depreciação (Depreciation Schedule)
    "account_asset.menu_action_account_report_assets",
    # Plano de Contas (Chart of Accounts)
    "account.menu_action_account_form",
    # Atualizar Grelhas de Impostos (Update Tax Grids)
    "l10n_pt_certificate.update_tax_grid_wizard_menu",
    # SAF-T (Exportação de SAF-T)
    "l10n_pt_certificate.saft_wizard_menu",
]

# Menus to block when certification contract is expired/not_found
CERT_BLOCKED_MENUS = [
    "l10n_pt_certificate.saft_wizard_menu",
]
