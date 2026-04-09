# Daily Improvement Backlog

## Queue
5. Implement create_catalog_variable_choice tool
6. Implement create_ui_policy tool
7. Implement create_ui_policy_action tool
8. Implement create_user_criteria tool
9. Implement create_user_criteria_condition tool
10. Implement execute_script_include tool
11. Add tests for changeset_tools.py (73% coverage)
12. Add tests for auth_manager.py (70% coverage)
13. Add tests for catalog_optimization.py (78% coverage)
14. Improve error messages across all tools
15. Add input validation for date fields across tools
16. Add pagination helpers for list operations
17. Add bulk operations support
18. Add retry logic with exponential backoff
19. Add rate limiting awareness
20. Add request/response logging in debug mode

## Completed
1. 2026-04-08 — Extract duplicated helpers (_get_instance_url, _get_headers, _unwrap_and_validate_params) from 8 tool files into src/servicenow_mcp/utils/helpers.py
2. 2026-04-08 — Implement list_syslog_entries tool (sys_log table, with filters for level/source/message/date range)
3. 2026-04-08 — Implement get_syslog_entry tool (fetch single entry by sys_id)
4. 2026-04-09 — Implement delete_catalog_item_variable tool (DELETE item_option_new/{sys_id})
