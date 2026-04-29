# Daily Improvement Backlog

## Queue
1. Implement delete_asset tool (DELETE alm_asset/{sys_id})
2. Implement list_asset_contracts tool (alm_contract table with filters)
3. Implement get_asset_contract tool (fetch single contract by sys_id)
4. Add create_asset to service_desk package in tool_packages.yaml
5. Add CI class filter to list_cis (currently only name/status/environment supported)

## Completed
1. 2026-04-08 — Extract duplicated helpers (_get_instance_url, _get_headers, _unwrap_and_validate_params) from 8 tool files into src/servicenow_mcp/utils/helpers.py
2. 2026-04-08 — Implement list_syslog_entries tool (sys_log table, with filters for level/source/message/date range)
3. 2026-04-08 — Implement get_syslog_entry tool (fetch single entry by sys_id)
4. 2026-04-09 — Implement delete_catalog_item_variable tool (DELETE item_option_new/{sys_id})
5. 2026-04-11 — Implement create_catalog_variable_choice tool (POST question_choice; links choices to select-type variables)
6. 2026-04-12 — Implement create_ui_policy tool (POST sys_ui_policy; supports conditions, on_load, reverse_if_false, catalog scoping)
7. 2026-04-13 — Implement create_ui_policy_action tool (POST sys_ui_policy_action; mandatory/visible/disabled field behaviours with leave_alone default)
8. 2026-04-14 — Implement create_user_criteria tool (POST user_criteria; role/group/department/company/location/script conditions with match_all flag)
9. 2026-04-15 — Implement create_user_criteria_condition tool (junction records linking user_criteria to catalog item/category/catalog; can_see and cannot_see visibility modes)
10. 2026-04-16 — Implement execute_script_include tool (POST /api/now/v1/scripting/eval; resolves class by name/sys_id, constructs JS snippet, deserialises JSON output)
11. 2026-04-17 — Add tests for changeset_tools.py and auth_manager.py; both modules reach 100% coverage (timeframe="recent" branch, update_changeset error paths, basic auth header encoding)
12. 2026-04-18 — Add tests for catalog_optimization.py; module reaches 100% coverage (error paths, category filters, vague-term detection, all optional update fields, _get_high_abandonment_items direct call)
13. 2026-04-19 — Improve error messages across all tools; added _format_http_error() to helpers.py that extracts ServiceNow JSON error body (error.message + error.detail), applied to all 19 tool files (140 call-sites); standardised logger format in syslog_tools.py and helpers.py
14. 2026-04-20 — Add input validation for date fields across tools; added validate_servicenow_datetime, validate_servicenow_date, validate_duration_hhmmss to helpers.py; applied @field_validator to 9 models in 5 tool files; 42 new tests
15. 2026-04-21 — Add pagination helpers for list operations; added _build_sysparm_params, _join_query_parts, _paginated_list_response to helpers.py; refactored incident_tools, syslog_tools, knowledge_base list operations; responses now include has_more/next_offset; 46 new tests
16. 2026-04-22 — Add bulk operations support; new execute_bulk_operations tool wraps POST /api/now/v1/batch; up to 100 sub-requests per call; auto-normalises methods and URLs; per-request ok/status_code in results; 24 new tests; bulk_tools.py at 100% coverage
17. 2026-04-23 — Add retry logic with exponential backoff; _make_request() in helpers.py retries on 429/500/502/503/504 and ConnectionError/Timeout; honours Retry-After header; applied to all 20 tool files; 30 new tests
19. 2026-04-24 — Add rate limiting awareness; RateLimitTracker class parses X-RateLimit-* headers, warns below 10% quota, sleeps proactively below 5%; integrated into _make_request() as module-level singleton; 34 new tests
20. 2026-04-25 — Add request/response logging in debug mode; _redact_headers() masks Authorization/Cookie/API-key headers; _truncate_body() serialises and truncates at 500 chars; _make_request() emits DEBUG lines before each attempt and after each response; 28 new tests
21. 2026-04-26 — Add CMDB configuration item tools (list_cis, get_ci, create_ci, update_ci); cmdb_tools.py supports cmdb_ci base table and any subclass; filters for name/class/status/environment; 45 new tests; 98% coverage
22. 2026-04-27 — Add CMDB relationship tools (list_ci_relationships, get_ci_relationship, create_ci_relationship, delete_ci_relationship, list_ci_relationship_types); cmdb_relationship_tools.py manages cmdb_rel_ci and cmdb_rel_type tables; normalises reference dict values; 42 new tests; 98% coverage
23. 2026-04-28 — Add asset management tools (list_assets, get_asset, update_asset); asset_tools.py targets alm_asset table; filters for tag/name/status/assignee/category; get_asset resolves by sys_id or asset tag; reference fields normalised to display values; 35 new tests; 99% coverage
24. 2026-04-29 — Add create_asset tool with alm_hardware subclass support; CreateAssetParams covers 14 hardware-specific fields (CPU/RAM/disk/OS/network); _format_asset conditionally includes hardware fields; tool registered in __init__.py, tool_utils.py, tool_packages.yaml; 16 new tests; 99% coverage
