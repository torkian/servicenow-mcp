# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [3.1.0] - 2026-06-16

### Added

- **Change approvals**: four new tools for the change-approval workflow — `list_change_approvals`, `get_change_approval`, `approve_change_approval`, and `reject_change_approval` — bringing the total tool surface to 180.

### Changed

- Test suite grows to 1,665 passing tests covering the new change-approval tools.

## [3.0.0] - 2026-06-13

### Added

- Expands the MCP tool surface from 89 to 176 tools (87 net-new across 16 new modules).
- **CMDB**: CI lifecycle management, class discovery, CI lookup by name, CI relationships and relationship types, and CI outage management.
- **Asset Management**: asset lifecycle operations, asset contracts, contract expiration, and contract-asset listing.
- **Problem Management**: create, retrieve, update, close, and list problems.
- **Service Requests / RITM**: request lifecycle operations and request-item listing.
- **SLA**: retrieve and list SLAs, manage SLA breaches, and list SLA-breach definitions.
- **Incident extras**: incident tasks, incident comments, incident deletion, incident reopening, and `escalate_incident` (priority change + group reassignment).
- **Change extras**: change tasks, change-request cancellation, and change-request reopening.
- **Bulk operations**: incidents, problems, change requests, and generic bulk execution.
- **Users, groups, roles & criteria**: membership management, role assignment, user criteria, and `get_user_by_email`.
- **Attachments**: upload, retrieval, listing, and deletion.
- **UI Policy**: create UI policies and UI policy actions.
- **Catalog extras**: catalog lookup, catalog listing, variable sets, and variable choices.
- **Notifications & syslog**: notification listing and syslog retrieval.
- **Script include execution**.
- **Knowledge**: article creation and category-based article listing.

### Changed

- Extracts shared helpers into `utils/helpers.py` and `utils/tool_utils.py` (pagination, rate limiting, retry logic, date validation), removing ~740 lines of duplication.
- Modernized Ruff configuration and sorted imports.

### Fixed

- Restores the test suite to 1,604 passing tests (0 failures).
- Removes 3 orphaned test files that blocked pytest collection; fixes 10 drifted tests.
- Hardens the swap-tolerant `_get_instance_url` helper.
- Narrows blind `assertRaises(Exception)` calls to specific exception types.

## [2.0.0]

### Added
- Service Catalog Task (SCTASK) management: `get_sctask`, `list_sctasks`, `update_sctask`.
- Time Card management: `list_time_cards`, `create_time_card`, `update_time_card`.
- `create_catalog_item` for creating new service catalog items.

### Fixed
- Boolean-logic bug in `update_sctask` sys_id resolution.
- Dockerfile not copying the `config/` directory.
- OAuth token response bodies logged in plaintext.
