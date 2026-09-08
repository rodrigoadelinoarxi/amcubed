# Contract Instance Checker

**Module:** `contract_instance_checker`  
**Version:** `18.0.2.0.11`  
**Author:** FlyByOdoo  
**License:** LGPL-3

## 1. Purpose

`contract_instance_checker` is the client-side contract enforcement module installed on controlled Odoo instances.

It validates each configured company contract against the central ARXI Contract Control API and applies runtime restrictions based on the returned contract status and type.

## 2. Current Scope and Behavior

### 2.1 Company scope (PT/AO)

Validation and banner logic are designed for companies in Portugal (`PT`) and Angola (`AO`).

- Daily cron validates companies with `contract_token` configured, then filters to PT/AO companies.
- Banner visibility is also conditioned by current company country (`is_pt_or_ao_company`).

### 2.2 Full block vs partial restriction

Contract types are split in two operational groups:

- **Full block types:** `flybyodoo`, `therabox`
  - Can trigger login denial (`AccessDenied`) when instance is blocked.
  - Can show full-screen block modal in the backend UI.
- **Non-full-block types:** e.g. `certification`, `payroll`, `support`, `fee_support`
  - Do not perform full login block.
  - When expired/not found, selected accounting/reporting actions are blocked during action load (`/web/action/load`, `/web/action/load_breadcrumbs`).

### 2.3 User counter visibility

For these contract types, user quota information is intentionally hidden:

- `certification`
- `payroll`

This is controlled by `NO_USER_INFO_TYPES` and exposed as `show_user_info` in settings/banner data.

### 2.4 Neutralized databases

If `database.is_neutralized` is enabled:

- Login blocking is disabled.
- Blocking modal is disabled.
- Banner remains visible in warning style for visibility/testing.

## 3. Validation Flow

### 3.1 Automatic validation (cron)

Installed cron:

- **Name:** `Instance Checker: Validate Contract Daily`
- **Method:** `contract.instance.status._cron_validate_contract()`
- **Interval:** daily

Per company flow:

1. Read `contract_nif`, `contract_token`, and central server URL (`contract_instance_checker.central_server_url`).
2. Count active internal users (excluding admin).
3. Call central endpoint:
   - `GET {central_server_url}/api/contract/check`
   - params: `nif`, `token`, `user_count`
4. Persist a status record in `contract.instance.status`.

### 3.2 API response mapping

Central API status is mapped locally as follows:

- `active` -> `active`
- `blocked` -> `expired` (treated as expired for local enforcement)
- `expired` -> `expired`
- `404` (not found) -> `not_found` + 48h grace period handling
- network/HTTP errors -> `error`

### 3.3 `not_found` grace period

For `not_found`:

- A 48-hour grace period is created (`grace_period_end`) if not already active.
- During grace period: no instance block.
- After grace period: only full-block types are blocked.

### 3.4 Manual validation

Two manual triggers are available:

- **Settings button:** `action_validate_now` (reloads settings page)
- **Banner button:** `action_force_validation_from_ui` (re-checks current company and refreshes banner state)

## 4. Enforcement Points

### 4.1 Login enforcement

`res.users._check_credentials()` is extended:

1. Odoo credential check runs first.
2. Contract block check runs next.
3. If blocked, raises `AccessDenied` with account manager contact details.

Exempt users:

- `base.user_admin`
- `base.user_root`

### 4.2 Action-load enforcement for inactive free contracts

`ir.actions.actions` is extended to prevent access to selected actions when:

- contract status is `expired` or `not_found`, and
- contract type is **not** in full-block types.

Guard applies during action loading routes and raises `AccessError` with restricted action names.

Blocked menus/actions are defined in `models/ir_ui_menu.py` (`INACTIVE_FREE_BLOCKED_MENUS`) and include selected accounting/reporting menus (Assets, Portuguese reports, tax grids, chart of accounts, etc.).

### 4.3 Frontend banner + modal

OWL component (`static/src/js/contract_banner.js`) periodically loads latest status and displays:

- warning/danger banner (expiring, user limit exceeded, expired, not found, error), and
- blocking modal only for full-block types when `is_instance_blocked` is true and DB is not neutralized.

Contact button is based on account manager email returned by central API.

## 5. Data Model

Primary model: `contract.instance.status`

Main persisted fields:

- `company_id`
- `last_check_date`
- `contract_status` (`active`, `expired`, `error`, `not_found`)
- `end_date`
- `user_limit`
- `current_user_count`
- `block_instance`
- `grace_period_end`
- `days_until_expiration`
- `error_message`
- `contract_name`
- `contract_type`
- `account_manager_name`
- `account_manager_email`

Computed indicators:

- `is_expiring_soon`
- `is_user_limit_exceeded`
- `is_instance_blocked`
- `is_in_grace_period`

Company extension (`res.company`):

- `contract_nif`
- `contract_token`
- `contract_central_server_url`
- `contract_type` (persisted from API for consistent UI behavior)

## 6. Settings and Configuration

Settings app section: **Contract** (`res.config.settings` inheritance)

Main parameters:

- **Instance NIF** (`company_id.contract_nif`)
- **Contract Code** (`company_id.contract_token`)
- **Central Server URL** (`contract_instance_checker.central_server_url`, default `https://contract.arxi.pt`)

Status information shown in settings includes:

- current contract status
- end date and remaining days
- user count/limit when applicable
- quick validation button

## 7. Access Rights

`security/ir.model.access.csv`:

- `base.group_user`: read `contract.instance.status`
- `base.group_system`: full access `contract.instance.status`

## 8. Installation

1. Add module path to addons.
2. Update apps list.
3. Install **Contract Instance Checker**.
4. Configure NIF + Contract Code in Settings.
5. Validate manually once.

## 9. Operational Notes

- This module depends on central server contract data quality (NIF/token correctness, contract type assignment, and manager contact data).
- For PT/AO multi-company environments, validation and visibility depend on currently selected company.
- For certification/payroll contracts, hiding user counters is expected behavior (not a bug).

