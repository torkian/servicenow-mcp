"""
Tools module for the ServiceNow MCP server.
"""

# Import tools as they are implemented
from servicenow_mcp.tools.catalog_optimization import (
    get_optimization_recommendations,
    update_catalog_item,
)
from servicenow_mcp.tools.catalog_tools import (
    create_catalog_category,
    create_catalog_item,
    get_catalog,
    get_catalog_item,
    list_catalog_categories,
    list_catalog_items,
    list_catalogs,
    move_catalog_items,
    update_catalog_category,
)
from servicenow_mcp.tools.catalog_variables import (
    create_catalog_item_variable,
    create_catalog_item_variable_set,
    create_catalog_variable_choice,
    delete_catalog_item_variable,
    list_catalog_item_variables,
    update_catalog_item_variable,
)
from servicenow_mcp.tools.change_tools import (
    add_change_task,
    approve_change,
    cancel_change_request,
    create_change_request,
    create_change_task,
    get_change_request_details,
    list_change_requests,
    list_change_tasks,
    reject_change,
    reopen_change_request,
    submit_change_for_approval,
    update_change_request,
)
from servicenow_mcp.tools.changeset_tools import (
    add_file_to_changeset,
    commit_changeset,
    create_changeset,
    get_changeset_details,
    list_changesets,
    publish_changeset,
    update_changeset,
)
from servicenow_mcp.tools.incident_tools import (
    add_comment,
    create_incident,
    delete_incident,
    escalate_incident,
    list_incidents,
    reopen_incident,
    resolve_incident,
    update_incident,
    get_incident_by_number,
)
from servicenow_mcp.tools.incident_task_tools import (
    close_incident_task,
    create_incident_task,
    list_incident_comments,
    list_incident_tasks,
)
from servicenow_mcp.tools.knowledge_base import (
    create_article,
    create_category,
    create_knowledge_article,
    create_knowledge_base,
    get_article,
    list_articles,
    list_articles_by_category,
    list_knowledge_bases,
    publish_article,
    update_article,
    list_categories,
)
from servicenow_mcp.tools.script_include_tools import (
    create_script_include,
    delete_script_include,
    execute_script_include,
    get_script_include,
    list_script_includes,
    update_script_include,
)
from servicenow_mcp.tools.user_tools import (
    create_user,
    update_user,
    get_user,
    get_user_by_email,
    list_users,
    create_group,
    update_group,
    add_group_members,
    remove_group_members,
    list_groups,
)
from servicenow_mcp.tools.workflow_tools import (
    activate_workflow,
    add_workflow_activity,
    create_workflow,
    deactivate_workflow,
    delete_workflow_activity,
    get_workflow_activities,
    get_workflow_details,
    list_workflow_versions,
    list_workflows,
    reorder_workflow_activities,
    update_workflow,
    update_workflow_activity,
)
from servicenow_mcp.tools.story_tools import (
    create_story,
    update_story,
    list_stories,
    list_story_dependencies,
    create_story_dependency,
    delete_story_dependency,
)
from servicenow_mcp.tools.epic_tools import (
    create_epic,
    update_epic,
    list_epics,
)
from servicenow_mcp.tools.scrum_task_tools import (
    create_scrum_task,
    update_scrum_task,
    list_scrum_tasks,
)
from servicenow_mcp.tools.project_tools import (
    create_project,
    update_project,
    list_projects,
)
from servicenow_mcp.tools.sctask_tools import (
    get_sctask,
    list_sctasks,
    update_sctask,
)
from servicenow_mcp.tools.time_card_tools import (
    list_time_cards,
    create_time_card,
    update_time_card,
)
from servicenow_mcp.tools.syslog_tools import (
    list_syslog_entries,
    get_syslog_entry,
)
from servicenow_mcp.tools.ui_policy_tools import (
    create_ui_policy,
    create_ui_policy_action,
)
from servicenow_mcp.tools.user_criteria_tools import (
    create_user_criteria,
    create_user_criteria_condition,
    list_catalog_item_user_criteria,
)
from servicenow_mcp.tools.bulk_tools import (
    bulk_update_change_requests,
    bulk_update_incidents,
    bulk_update_problems,
    execute_bulk_operations,
)
from servicenow_mcp.tools.cmdb_tools import (
    create_ci,
    create_ci_outage,
    delete_ci_outage,
    get_ci,
    get_ci_by_name,
    get_ci_outage,
    list_cmdb_classes,
    list_cmdb_ci_outages,
    list_cis,
    update_ci,
    update_ci_outage,
)
from servicenow_mcp.tools.cmdb_relationship_tools import (
    create_ci_relationship,
    delete_ci_relationship,
    get_ci_relationship,
    list_ci_relationships,
    list_ci_relationship_types,
)
from servicenow_mcp.tools.asset_tools import (
    create_asset,
    delete_asset,
    list_assets,
    get_asset,
    update_asset,
)
from servicenow_mcp.tools.contract_tools import (
    list_asset_contracts,
    get_asset_contract,
    create_asset_contract,
    update_asset_contract,
    expire_asset_contract,
    list_contract_assets,
)
from servicenow_mcp.tools.attachment_tools import (
    list_attachments,
    get_attachment,
    delete_attachment,
    upload_attachment,
    download_attachment,
)
from servicenow_mcp.tools.problem_tools import (
    close_problem,
    create_problem,
    get_problem,
    list_problems,
    update_problem,
)
from servicenow_mcp.tools.sla_tools import (
    get_sla,
    get_sla_breach,
    list_sla_breach_definitions,
    list_sla_breaches,
    list_slas,
    resolve_sla_breach,
)
from servicenow_mcp.tools.request_tools import (
    create_request,
    get_request,
    list_request_items,
    list_requests,
    update_request,
)
from servicenow_mcp.tools.notification_tools import (
    list_notifications,
)
from servicenow_mcp.tools.role_tools import (
    assign_role_to_group,
    get_group_roles,
    list_user_roles,
    remove_role_from_group,
)
from servicenow_mcp.tools.user_group_tools import (
    add_user_to_group,
    get_user_group,
    list_group_members,
    list_user_groups,
    remove_user_from_group,
)

__all__ = [
    # Incident tools
    "create_incident",
    "update_incident",
    "delete_incident",
    "escalate_incident",
    "add_comment",
    "resolve_incident",
    "reopen_incident",
    "list_incidents",
    "get_incident_by_number",
    # Incident Task tools
    "create_incident_task",
    "list_incident_tasks",
    "list_incident_comments",
    "close_incident_task",
    
    # Catalog tools
    "list_catalogs",
    "get_catalog",
    "create_catalog_item",
    "list_catalog_items",
    "get_catalog_item",
    "list_catalog_categories",
    "create_catalog_category",
    "update_catalog_category",
    "move_catalog_items",
    "get_optimization_recommendations",
    "update_catalog_item",
    "create_catalog_item_variable",
    "create_catalog_item_variable_set",
    "list_catalog_item_variables",
    "update_catalog_item_variable",
    "delete_catalog_item_variable",
    "create_catalog_variable_choice",
    
    # Change management tools
    "create_change_request",
    "update_change_request",
    "list_change_requests",
    "get_change_request_details",
    "add_change_task",
    "list_change_tasks",
    "create_change_task",
    "submit_change_for_approval",
    "approve_change",
    "reject_change",
    "cancel_change_request",
    "reopen_change_request",
    
    # Workflow management tools
    "list_workflows",
    "get_workflow_details",
    "list_workflow_versions",
    "get_workflow_activities",
    "create_workflow",
    "update_workflow",
    "activate_workflow",
    "deactivate_workflow",
    "add_workflow_activity",
    "update_workflow_activity",
    "delete_workflow_activity",
    "reorder_workflow_activities",
    
    # Changeset tools
    "list_changesets",
    "get_changeset_details",
    "create_changeset",
    "update_changeset",
    "commit_changeset",
    "publish_changeset",
    "add_file_to_changeset",
    
    # Script Include tools
    "list_script_includes",
    "get_script_include",
    "create_script_include",
    "update_script_include",
    "delete_script_include",
    "execute_script_include",
    
    # Knowledge Base tools
    "create_knowledge_base",
    "list_knowledge_bases",
    "create_category",
    "list_categories",
    "create_article",
    "create_knowledge_article",
    "update_article",
    "publish_article",
    "list_articles",
    "list_articles_by_category",
    "get_article",
    
    # User management tools
    "create_user",
    "update_user",
    "get_user",
    "list_users",
    "create_group",
    "update_group",
    "add_group_members",
    "remove_group_members",
    "list_groups",

    # Story tools
    "create_story",
    "update_story",
    "list_stories",
    "list_story_dependencies",
    "create_story_dependency",
    "delete_story_dependency",
    
    # Epic tools
    "create_epic",
    "update_epic",
    "list_epics",

    # Scrum Task tools
    "create_scrum_task",
    "update_scrum_task",
    "list_scrum_tasks",

    # Project tools
    "create_project",
    "update_project",
    "list_projects",

    # Service Catalog Task tools
    "get_sctask",
    "list_sctasks",
    "update_sctask",

    # Time Card tools
    "list_time_cards",
    "create_time_card",
    "update_time_card",

    # Syslog tools
    "list_syslog_entries",
    "get_syslog_entry",

    # UI Policy tools
    "create_ui_policy",
    "create_ui_policy_action",

    # User Criteria tools
    "create_user_criteria",
    "create_user_criteria_condition",
    "list_catalog_item_user_criteria",

    # Bulk operations
    "execute_bulk_operations",
    "bulk_update_incidents",
    "bulk_update_change_requests",
    "bulk_update_problems",

    # CMDB tools
    "list_cmdb_classes",
    "list_cis",
    "get_ci",
    "get_ci_by_name",
    "create_ci",
    "update_ci",
    "list_cmdb_ci_outages",
    "get_ci_outage",
    "create_ci_outage",
    "update_ci_outage",
    "delete_ci_outage",

    # CMDB relationship tools
    "list_ci_relationships",
    "get_ci_relationship",
    "create_ci_relationship",
    "delete_ci_relationship",
    "list_ci_relationship_types",

    # Asset management tools
    "create_asset",
    "delete_asset",
    "list_assets",
    "get_asset",
    "update_asset",

    # Contract management tools
    "list_asset_contracts",
    "get_asset_contract",
    "create_asset_contract",
    "update_asset_contract",
    "expire_asset_contract",
    "list_contract_assets",

    # Attachment tools
    "list_attachments",
    "get_attachment",
    "delete_attachment",
    "upload_attachment",
    "download_attachment",

    # Problem management tools
    "list_problems",
    "get_problem",
    "create_problem",
    "update_problem",
    "close_problem",

    # SLA management tools
    "list_slas",
    "get_sla",
    "list_sla_breach_definitions",
    "list_sla_breaches",
    "get_sla_breach",
    "resolve_sla_breach",

    # User email lookup
    "get_user_by_email",

    # Service Request tools
    "list_requests",
    "get_request",
    "create_request",
    "update_request",
    "list_request_items",

    # User Group tools
    "list_user_groups",
    "get_user_group",
    "add_user_to_group",
    "remove_user_from_group",
    "list_group_members",

    # Role management tools
    "get_group_roles",
    "assign_role_to_group",
    "remove_role_from_group",
    "list_user_roles",

    # Notification tools
    "list_notifications",
]
