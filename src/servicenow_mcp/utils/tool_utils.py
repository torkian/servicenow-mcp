from typing import Any, Callable, Dict, Tuple, Type

# Import all necessary tool implementation functions and params models
# (This list needs to be kept complete and up-to-date)
from servicenow_mcp.tools.catalog_optimization import (
    OptimizationRecommendationsParams,
    UpdateCatalogItemParams,
)
from servicenow_mcp.tools.catalog_optimization import (
    get_optimization_recommendations as get_optimization_recommendations_tool,
)
from servicenow_mcp.tools.catalog_optimization import (
    update_catalog_item as update_catalog_item_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    CreateCatalogCategoryParams,
    CreateCatalogItemParams,
    GetCatalogItemParams,
    ListCatalogCategoriesParams,
    ListCatalogItemsParams,
    MoveCatalogItemsParams,
    UpdateCatalogCategoryParams,
)
from servicenow_mcp.tools.catalog_tools import (
    create_catalog_category as create_catalog_category_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    create_catalog_item as create_catalog_item_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    get_catalog_item as get_catalog_item_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    list_catalog_categories as list_catalog_categories_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    list_catalog_items as list_catalog_items_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    move_catalog_items as move_catalog_items_tool,
)
from servicenow_mcp.tools.catalog_tools import (
    update_catalog_category as update_catalog_category_tool,
)
from servicenow_mcp.tools.catalog_variables import (
    CatalogItemVariableSetResponse,
    CatalogVariableChoiceResponse,
    CreateCatalogItemVariableParams,
    CreateCatalogItemVariableSetParams,
    CreateCatalogVariableChoiceParams,
    DeleteCatalogItemVariableParams,
    ListCatalogItemVariablesParams,
    UpdateCatalogItemVariableParams,
)
from servicenow_mcp.tools.catalog_variables import (
    create_catalog_item_variable as create_catalog_item_variable_tool,
)
from servicenow_mcp.tools.catalog_variables import (
    create_catalog_item_variable_set as create_catalog_item_variable_set_tool,
)
from servicenow_mcp.tools.catalog_variables import (
    create_catalog_variable_choice as create_catalog_variable_choice_tool,
)
from servicenow_mcp.tools.catalog_variables import (
    delete_catalog_item_variable as delete_catalog_item_variable_tool,
)
from servicenow_mcp.tools.catalog_variables import (
    list_catalog_item_variables as list_catalog_item_variables_tool,
)
from servicenow_mcp.tools.catalog_variables import (
    update_catalog_item_variable as update_catalog_item_variable_tool,
)
from servicenow_mcp.tools.change_tools import (
    AddChangeTaskParams,
    ApproveChangeParams,
    CreateChangeRequestParams,
    GetChangeRequestDetailsParams,
    ListChangeRequestsParams,
    RejectChangeParams,
    SubmitChangeForApprovalParams,
    UpdateChangeRequestParams,
)
from servicenow_mcp.tools.change_tools import (
    add_change_task as add_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    approve_change as approve_change_tool,
)
from servicenow_mcp.tools.change_tools import (
    create_change_request as create_change_request_tool,
)
from servicenow_mcp.tools.change_tools import (
    get_change_request_details as get_change_request_details_tool,
)
from servicenow_mcp.tools.change_tools import (
    list_change_requests as list_change_requests_tool,
)
from servicenow_mcp.tools.change_tools import (
    reject_change as reject_change_tool,
)
from servicenow_mcp.tools.change_tools import (
    submit_change_for_approval as submit_change_for_approval_tool,
)
from servicenow_mcp.tools.change_tools import (
    update_change_request as update_change_request_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    AddFileToChangesetParams,
    CommitChangesetParams,
    CreateChangesetParams,
    GetChangesetDetailsParams,
    ListChangesetsParams,
    PublishChangesetParams,
    UpdateChangesetParams,
)
from servicenow_mcp.tools.changeset_tools import (
    add_file_to_changeset as add_file_to_changeset_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    commit_changeset as commit_changeset_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    create_changeset as create_changeset_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    get_changeset_details as get_changeset_details_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    list_changesets as list_changesets_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    publish_changeset as publish_changeset_tool,
)
from servicenow_mcp.tools.changeset_tools import (
    update_changeset as update_changeset_tool,
)
from servicenow_mcp.tools.incident_tools import (
    AddCommentParams,
    CreateIncidentParams,
    ListIncidentsParams,
    ResolveIncidentParams,
    UpdateIncidentParams,
    GetIncidentByNumberParams,
)
from servicenow_mcp.tools.incident_tools import (
    add_comment as add_comment_tool,
)
from servicenow_mcp.tools.incident_tools import (
    create_incident as create_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    list_incidents as list_incidents_tool,
)
from servicenow_mcp.tools.incident_tools import (
    resolve_incident as resolve_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    update_incident as update_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    get_incident_by_number as get_incident_by_number_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    CreateArticleParams,
    CreateKnowledgeBaseParams,
    GetArticleParams,
    ListArticlesParams,
    ListKnowledgeBasesParams,
    PublishArticleParams,
    UpdateArticleParams,
)
from servicenow_mcp.tools.knowledge_base import (
    CreateCategoryParams as CreateKBCategoryParams,  # Aliased
)
from servicenow_mcp.tools.knowledge_base import (
    ListCategoriesParams as ListKBCategoriesParams,  # Aliased
)
from servicenow_mcp.tools.knowledge_base import (
    create_article as create_article_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    # create_category aliased in function call
    create_knowledge_base as create_knowledge_base_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    get_article as get_article_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    list_articles as list_articles_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    # list_categories aliased in function call
    list_knowledge_bases as list_knowledge_bases_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    publish_article as publish_article_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    update_article as update_article_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    CreateScriptIncludeParams,
    DeleteScriptIncludeParams,
    ExecuteScriptIncludeParams,
    GetScriptIncludeParams,
    ListScriptIncludesParams,
    ScriptIncludeResponse,
    UpdateScriptIncludeParams,
)
from servicenow_mcp.tools.script_include_tools import (
    create_script_include as create_script_include_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    delete_script_include as delete_script_include_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    execute_script_include as execute_script_include_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    get_script_include as get_script_include_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    list_script_includes as list_script_includes_tool,
)
from servicenow_mcp.tools.script_include_tools import (
    update_script_include as update_script_include_tool,
)
from servicenow_mcp.tools.user_tools import (
    AddGroupMembersParams,
    CreateGroupParams,
    CreateUserParams,
    GetUserParams,
    ListGroupsParams,
    ListUsersParams,
    RemoveGroupMembersParams,
    UpdateGroupParams,
    UpdateUserParams,
)
from servicenow_mcp.tools.user_tools import (
    add_group_members as add_group_members_tool,
)
from servicenow_mcp.tools.user_tools import (
    create_group as create_group_tool,
)
from servicenow_mcp.tools.user_tools import (
    create_user as create_user_tool,
)
from servicenow_mcp.tools.user_tools import (
    get_user as get_user_tool,
)
from servicenow_mcp.tools.user_tools import (
    list_groups as list_groups_tool,
)
from servicenow_mcp.tools.user_tools import (
    list_users as list_users_tool,
)
from servicenow_mcp.tools.user_tools import (
    remove_group_members as remove_group_members_tool,
)
from servicenow_mcp.tools.user_tools import (
    update_group as update_group_tool,
)
from servicenow_mcp.tools.user_tools import (
    update_user as update_user_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    ActivateWorkflowParams,
    AddWorkflowActivityParams,
    CreateWorkflowParams,
    DeactivateWorkflowParams,
    DeleteWorkflowActivityParams,
    GetWorkflowActivitiesParams,
    GetWorkflowDetailsParams,
    ListWorkflowsParams,
    ListWorkflowVersionsParams,
    ReorderWorkflowActivitiesParams,
    UpdateWorkflowActivityParams,
    UpdateWorkflowParams,
)
from servicenow_mcp.tools.workflow_tools import (
    activate_workflow as activate_workflow_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    add_workflow_activity as add_workflow_activity_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    create_workflow as create_workflow_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    deactivate_workflow as deactivate_workflow_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    delete_workflow_activity as delete_workflow_activity_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    get_workflow_activities as get_workflow_activities_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    get_workflow_details as get_workflow_details_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    list_workflow_versions as list_workflow_versions_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    list_workflows as list_workflows_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    reorder_workflow_activities as reorder_workflow_activities_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    update_workflow as update_workflow_tool,
)
from servicenow_mcp.tools.workflow_tools import (
    update_workflow_activity as update_workflow_activity_tool,
)
from servicenow_mcp.tools.story_tools import (
    CreateStoryParams,
    UpdateStoryParams,
    ListStoriesParams,
    ListStoryDependenciesParams,
    CreateStoryDependencyParams,
    DeleteStoryDependencyParams,
)
from servicenow_mcp.tools.story_tools import (
    create_story as create_story_tool,
    update_story as update_story_tool,
    list_stories as list_stories_tool,
    list_story_dependencies as list_story_dependencies_tool,
    create_story_dependency as create_story_dependency_tool,
    delete_story_dependency as delete_story_dependency_tool,
)
from servicenow_mcp.tools.epic_tools import (
    CreateEpicParams,
    UpdateEpicParams,
    ListEpicsParams,
)
from servicenow_mcp.tools.epic_tools import (
    create_epic as create_epic_tool,
    update_epic as update_epic_tool,
    list_epics as list_epics_tool,
)
from servicenow_mcp.tools.scrum_task_tools import (
    CreateScrumTaskParams,
    UpdateScrumTaskParams,
    ListScrumTasksParams,
)
from servicenow_mcp.tools.scrum_task_tools import (
    create_scrum_task as create_scrum_task_tool,
    update_scrum_task as update_scrum_task_tool,
    list_scrum_tasks as list_scrum_tasks_tool,
)
from servicenow_mcp.tools.project_tools import (
    CreateProjectParams,
    UpdateProjectParams,
    ListProjectsParams,
)
from servicenow_mcp.tools.project_tools import (
    create_project as create_project_tool,
    update_project as update_project_tool,
    list_projects as list_projects_tool,
)
from servicenow_mcp.tools.sctask_tools import (
    GetSCTaskParams,
    UpdateSCTaskParams,
    ListSCTasksParams,
)
from servicenow_mcp.tools.sctask_tools import (
    get_sctask as get_sctask_tool,
    list_sctasks as list_sctasks_tool,
    update_sctask as update_sctask_tool,
)
from servicenow_mcp.tools.time_card_tools import (
    ListTimeCardsParams,
    CreateTimeCardParams,
    UpdateTimeCardParams,
)
from servicenow_mcp.tools.time_card_tools import (
    list_time_cards as list_time_cards_tool,
    create_time_card as create_time_card_tool,
    update_time_card as update_time_card_tool,
)
from servicenow_mcp.tools.syslog_tools import (
    ListSyslogEntriesParams,
    GetSyslogEntryParams,
)
from servicenow_mcp.tools.syslog_tools import (
    list_syslog_entries as list_syslog_entries_tool,
    get_syslog_entry as get_syslog_entry_tool,
)
from servicenow_mcp.tools.ui_policy_tools import (
    CreateUIPolicyParams,
    CreateUIPolicyActionParams,
)
from servicenow_mcp.tools.ui_policy_tools import (
    create_ui_policy as create_ui_policy_tool,
    create_ui_policy_action as create_ui_policy_action_tool,
)
from servicenow_mcp.tools.user_criteria_tools import (
    CreateUserCriteriaConditionParams,
    CreateUserCriteriaParams,
)
from servicenow_mcp.tools.user_criteria_tools import (
    create_user_criteria as create_user_criteria_tool,
)
from servicenow_mcp.tools.user_criteria_tools import (
    create_user_criteria_condition as create_user_criteria_condition_tool,
)
from servicenow_mcp.tools.bulk_tools import BulkOperationsParams
from servicenow_mcp.tools.bulk_tools import (
    execute_bulk_operations as execute_bulk_operations_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    CreateCIParams,
    GetCIParams,
    ListCIsParams,
    UpdateCIParams,
)
from servicenow_mcp.tools.cmdb_tools import (
    create_ci as create_ci_tool,
    get_ci as get_ci_tool,
    list_cis as list_cis_tool,
    update_ci as update_ci_tool,
)
from servicenow_mcp.tools.cmdb_relationship_tools import (
    CreateCIRelationshipParams,
    DeleteCIRelationshipParams,
    GetCIRelationshipParams,
    ListCIRelationshipsParams,
    ListCIRelationshipTypesParams,
)
from servicenow_mcp.tools.cmdb_relationship_tools import (
    create_ci_relationship as create_ci_relationship_tool,
    delete_ci_relationship as delete_ci_relationship_tool,
    get_ci_relationship as get_ci_relationship_tool,
    list_ci_relationships as list_ci_relationships_tool,
    list_ci_relationship_types as list_ci_relationship_types_tool,
)
from servicenow_mcp.tools.asset_tools import (
    CreateAssetParams,
    DeleteAssetParams,
    GetAssetParams,
    ListAssetsParams,
    UpdateAssetParams,
)
from servicenow_mcp.tools.asset_tools import (
    create_asset as create_asset_tool,
    delete_asset as delete_asset_tool,
    get_asset as get_asset_tool,
    list_assets as list_assets_tool,
    update_asset as update_asset_tool,
)
from servicenow_mcp.tools.contract_tools import (
    CreateAssetContractParams,
    ExpireAssetContractParams,
    GetAssetContractParams,
    ListAssetContractsParams,
    ListContractAssetsParams,
    UpdateAssetContractParams,
)
from servicenow_mcp.tools.contract_tools import (
    create_asset_contract as create_asset_contract_tool,
    expire_asset_contract as expire_asset_contract_tool,
    get_asset_contract as get_asset_contract_tool,
    list_asset_contracts as list_asset_contracts_tool,
    list_contract_assets as list_contract_assets_tool,
    update_asset_contract as update_asset_contract_tool,
)
from servicenow_mcp.tools.attachment_tools import (
    DeleteAttachmentParams,
    GetAttachmentParams,
    ListAttachmentsParams,
)
from servicenow_mcp.tools.attachment_tools import (
    delete_attachment as delete_attachment_tool,
    get_attachment as get_attachment_tool,
    list_attachments as list_attachments_tool,
)

# Define a type alias for the Pydantic models or dataclasses used for params
ParamsModel = Type[Any]  # Use Type[Any] for broader compatibility initially

# Define the structure of the tool definition tuple
ToolDefinition = Tuple[
    Callable,  # Implementation function
    ParamsModel,  # Pydantic model for parameters
    Type,  # Return type annotation (used for hints, not strictly enforced by low-level server)
    str,  # Description
    str,  # Serialization method ('str', 'json', 'dict', 'model_dump', etc.)
]


def get_tool_definitions(
    create_kb_category_tool_impl: Callable, list_kb_categories_tool_impl: Callable
) -> Dict[str, ToolDefinition]:
    """
    Returns a dictionary containing definitions for all available ServiceNow tools.

    This centralizes the tool definitions for use in the server implementation.
    Pass aliased functions for KB categories directly.

    Returns:
        Dict[str, ToolDefinition]: A dictionary mapping tool names to their definitions.
    """
    tool_definitions: Dict[str, ToolDefinition] = {
        # Incident Tools
        "create_incident": (
            create_incident_tool,
            CreateIncidentParams,
            str,
            "Create a new incident in ServiceNow",
            "str",
        ),
        "update_incident": (
            update_incident_tool,
            UpdateIncidentParams,
            str,
            "Update an existing incident in ServiceNow",
            "str",
        ),
        "add_comment": (
            add_comment_tool,
            AddCommentParams,
            str,
            "Add a comment to an incident in ServiceNow",
            "str",
        ),
        "resolve_incident": (
            resolve_incident_tool,
            ResolveIncidentParams,
            str,
            "Resolve an incident in ServiceNow",
            "str",
        ),
        "list_incidents": (
            list_incidents_tool,
            ListIncidentsParams,
            str,  # Expects JSON string
            "List incidents from ServiceNow",
            "json",  # Tool returns list/dict, needs JSON dump
        ),
        "get_incident_by_number":(
            get_incident_by_number_tool,
            GetIncidentByNumberParams,
            str,
            "Incident details from ServiceNow",
            "json_dict"
        ),
        # Catalog Tools
        "list_catalog_items": (
            list_catalog_items_tool,
            ListCatalogItemsParams,
            str,  # Expects JSON string
            "List service catalog items.",
            "json",  # Tool returns list/dict
        ),
        "get_catalog_item": (
            get_catalog_item_tool,
            GetCatalogItemParams,
            str,  # Expects JSON string
            "Get a specific service catalog item.",
            "json_dict",  # Tool returns Pydantic model
        ),
        "list_catalog_categories": (
            list_catalog_categories_tool,
            ListCatalogCategoriesParams,
            str,  # Expects JSON string
            "List service catalog categories.",
            "json",  # Tool returns list/dict
        ),
        "create_catalog_category": (
            create_catalog_category_tool,
            CreateCatalogCategoryParams,
            str,  # Expects JSON string
            "Create a new service catalog category.",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_catalog_category": (
            update_catalog_category_tool,
            UpdateCatalogCategoryParams,
            str,  # Expects JSON string
            "Update an existing service catalog category.",
            "json_dict",  # Tool returns Pydantic model
        ),
        "move_catalog_items": (
            move_catalog_items_tool,
            MoveCatalogItemsParams,
            str,  # Expects JSON string
            "Move catalog items to a different category.",
            "json_dict",  # Tool returns Pydantic model
        ),
        "get_optimization_recommendations": (
            get_optimization_recommendations_tool,
            OptimizationRecommendationsParams,
            str,  # Expects JSON string
            "Get optimization recommendations for the service catalog.",
            "json",  # Tool returns list/dict
        ),
        "update_catalog_item": (
            update_catalog_item_tool,
            UpdateCatalogItemParams,
            str,  # Expects JSON string
            "Update a service catalog item.",
            "json",  # Tool returns Pydantic model
        ),
        "create_catalog_item": (
            create_catalog_item_tool,
            CreateCatalogItemParams,
            str,
            "Create a new service catalog item in ServiceNow",
            "json_dict",
        ),
        # Catalog Variables
        "create_catalog_item_variable": (
            create_catalog_item_variable_tool,
            CreateCatalogItemVariableParams,
            Dict[str, Any],  # Expects dict
            "Create a new catalog item variable",
            "dict",  # Tool returns Pydantic model
        ),
        "list_catalog_item_variables": (
            list_catalog_item_variables_tool,
            ListCatalogItemVariablesParams,
            Dict[str, Any],  # Expects dict
            "List catalog item variables",
            "dict",  # Tool returns Pydantic model
        ),
        "update_catalog_item_variable": (
            update_catalog_item_variable_tool,
            UpdateCatalogItemVariableParams,
            Dict[str, Any],  # Expects dict
            "Update a catalog item variable",
            "dict",  # Tool returns Pydantic model
        ),
        "delete_catalog_item_variable": (
            delete_catalog_item_variable_tool,
            DeleteCatalogItemVariableParams,
            Dict[str, Any],  # Expects dict
            "Delete a catalog item variable by sys_id",
            "dict",  # Tool returns Pydantic model
        ),
        "create_catalog_item_variable_set": (
            create_catalog_item_variable_set_tool,
            CreateCatalogItemVariableSetParams,
            CatalogItemVariableSetResponse,
            "Create a variable set (section) to group catalog item variables; optionally link to a catalog item",
            "dict",
        ),
        "create_catalog_variable_choice": (
            create_catalog_variable_choice_tool,
            CreateCatalogVariableChoiceParams,
            CatalogVariableChoiceResponse,
            "Create a choice option for a select-type catalog item variable",
            "dict",
        ),
        # Change Management Tools
        "create_change_request": (
            create_change_request_tool,
            CreateChangeRequestParams,
            str,
            "Create a new change request in ServiceNow",
            "str",
        ),
        "update_change_request": (
            update_change_request_tool,
            UpdateChangeRequestParams,
            str,
            "Update an existing change request in ServiceNow",
            "str",
        ),
        "list_change_requests": (
            list_change_requests_tool,
            ListChangeRequestsParams,
            str,  # Expects JSON string
            "List change requests from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "get_change_request_details": (
            get_change_request_details_tool,
            GetChangeRequestDetailsParams,
            str,  # Expects JSON string
            "Get detailed information about a specific change request",
            "json",  # Tool returns list/dict
        ),
        "add_change_task": (
            add_change_task_tool,
            AddChangeTaskParams,
            str,  # Expects JSON string
            "Add a task to a change request",
            "json_dict",  # Tool returns Pydantic model
        ),
        "submit_change_for_approval": (
            submit_change_for_approval_tool,
            SubmitChangeForApprovalParams,
            str,
            "Submit a change request for approval",
            "str",  # Tool returns simple message
        ),
        "approve_change": (
            approve_change_tool,
            ApproveChangeParams,
            str,
            "Approve a change request",
            "str",  # Tool returns simple message
        ),
        "reject_change": (
            reject_change_tool,
            RejectChangeParams,
            str,
            "Reject a change request",
            "str",  # Tool returns simple message
        ),
        # Workflow Management Tools
        "list_workflows": (
            list_workflows_tool,
            ListWorkflowsParams,
            str,  # Expects JSON string
            "List workflows from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "get_workflow_details": (
            get_workflow_details_tool,
            GetWorkflowDetailsParams,
            str,  # Expects JSON string
            "Get detailed information about a specific workflow",
            "json",  # Tool returns list/dict
        ),
        "list_workflow_versions": (
            list_workflow_versions_tool,
            ListWorkflowVersionsParams,
            str,  # Expects JSON string
            "List workflow versions from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "get_workflow_activities": (
            get_workflow_activities_tool,
            GetWorkflowActivitiesParams,
            str,  # Expects JSON string
            "Get activities for a specific workflow",
            "json",  # Tool returns list/dict
        ),
        "create_workflow": (
            create_workflow_tool,
            CreateWorkflowParams,
            str,  # Expects JSON string
            "Create a new workflow in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_workflow": (
            update_workflow_tool,
            UpdateWorkflowParams,
            str,  # Expects JSON string
            "Update an existing workflow in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "activate_workflow": (
            activate_workflow_tool,
            ActivateWorkflowParams,
            str,
            "Activate a workflow in ServiceNow",
            "str",  # Tool returns simple message
        ),
        "deactivate_workflow": (
            deactivate_workflow_tool,
            DeactivateWorkflowParams,
            str,
            "Deactivate a workflow in ServiceNow",
            "str",  # Tool returns simple message
        ),
        "add_workflow_activity": (
            add_workflow_activity_tool,
            AddWorkflowActivityParams,
            str,  # Expects JSON string
            "Add a new activity to a workflow in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_workflow_activity": (
            update_workflow_activity_tool,
            UpdateWorkflowActivityParams,
            str,  # Expects JSON string
            "Update an existing activity in a workflow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "delete_workflow_activity": (
            delete_workflow_activity_tool,
            DeleteWorkflowActivityParams,
            str,
            "Delete an activity from a workflow",
            "str",  # Tool returns simple message
        ),
        "reorder_workflow_activities": (
            reorder_workflow_activities_tool,
            ReorderWorkflowActivitiesParams,
            str,
            "Reorder activities in a workflow",
            "str",  # Tool returns simple message
        ),
        # Changeset Management Tools
        "list_changesets": (
            list_changesets_tool,
            ListChangesetsParams,
            str,  # Expects JSON string
            "List changesets from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "get_changeset_details": (
            get_changeset_details_tool,
            GetChangesetDetailsParams,
            str,  # Expects JSON string
            "Get detailed information about a specific changeset",
            "json",  # Tool returns list/dict
        ),
        "create_changeset": (
            create_changeset_tool,
            CreateChangesetParams,
            str,  # Expects JSON string
            "Create a new changeset in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_changeset": (
            update_changeset_tool,
            UpdateChangesetParams,
            str,  # Expects JSON string
            "Update an existing changeset in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "commit_changeset": (
            commit_changeset_tool,
            CommitChangesetParams,
            str,
            "Commit a changeset in ServiceNow",
            "str",  # Tool returns simple message
        ),
        "publish_changeset": (
            publish_changeset_tool,
            PublishChangesetParams,
            str,
            "Publish a changeset in ServiceNow",
            "str",  # Tool returns simple message
        ),
        "add_file_to_changeset": (
            add_file_to_changeset_tool,
            AddFileToChangesetParams,
            str,
            "Add a file to a changeset in ServiceNow",
            "str",  # Tool returns simple message
        ),
        # Script Include Tools
        "list_script_includes": (
            list_script_includes_tool,
            ListScriptIncludesParams,
            Dict[str, Any],  # Expects dict
            "List script includes from ServiceNow",
            "raw_dict",  # Tool returns raw dict
        ),
        "get_script_include": (
            get_script_include_tool,
            GetScriptIncludeParams,
            Dict[str, Any],  # Expects dict
            "Get a specific script include from ServiceNow",
            "raw_dict",  # Tool returns raw dict
        ),
        "create_script_include": (
            create_script_include_tool,
            CreateScriptIncludeParams,
            ScriptIncludeResponse,  # Expects Pydantic model
            "Create a new script include in ServiceNow",
            "raw_pydantic",  # Tool returns Pydantic model
        ),
        "update_script_include": (
            update_script_include_tool,
            UpdateScriptIncludeParams,
            ScriptIncludeResponse,  # Expects Pydantic model
            "Update an existing script include in ServiceNow",
            "raw_pydantic",  # Tool returns Pydantic model
        ),
        "delete_script_include": (
            delete_script_include_tool,
            DeleteScriptIncludeParams,
            str,  # Expects JSON string
            "Delete a script include in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "execute_script_include": (
            execute_script_include_tool,
            ExecuteScriptIncludeParams,
            Dict[str, Any],
            (
                "Execute a method on a ServiceNow Script Include and return its result. "
                "Resolves the script include by name or sys_id, then calls the specified "
                "method with optional positional arguments via the server-side scripting "
                "eval endpoint."
            ),
            "raw_dict",
        ),
        # Knowledge Base Tools
        "create_knowledge_base": (
            create_knowledge_base_tool,
            CreateKnowledgeBaseParams,
            str,  # Expects JSON string
            "Create a new knowledge base in ServiceNow",
            "json_dict",  # Tool returns Pydantic model
        ),
        "list_knowledge_bases": (
            list_knowledge_bases_tool,
            ListKnowledgeBasesParams,
            Dict[str, Any],  # Expects dict
            "List knowledge bases from ServiceNow",
            "raw_dict",  # Tool returns raw dict
        ),
        # Use the passed-in implementations for aliased KB category tools
        "create_category": (
            create_kb_category_tool_impl,  # Use passed function
            CreateKBCategoryParams,
            str,  # Expects JSON string
            "Create a new category in a knowledge base",
            "json_dict",  # Tool returns Pydantic model
        ),
        "create_article": (
            create_article_tool,
            CreateArticleParams,
            str,  # Expects JSON string
            "Create a new knowledge article",
            "json_dict",  # Tool returns Pydantic model
        ),
        "update_article": (
            update_article_tool,
            UpdateArticleParams,
            str,  # Expects JSON string
            "Update an existing knowledge article",
            "json_dict",  # Tool returns Pydantic model
        ),
        "publish_article": (
            publish_article_tool,
            PublishArticleParams,
            str,  # Expects JSON string
            "Publish a knowledge article",
            "json_dict",  # Tool returns Pydantic model
        ),
        "list_articles": (
            list_articles_tool,
            ListArticlesParams,
            Dict[str, Any],  # Expects dict
            "List knowledge articles",
            "raw_dict",  # Tool returns raw dict
        ),
        "get_article": (
            get_article_tool,
            GetArticleParams,
            Dict[str, Any],  # Expects dict
            "Get a specific knowledge article by ID",
            "raw_dict",  # Tool returns raw dict
        ),
        # Use the passed-in implementations for aliased KB category tools
        "list_categories": (
            list_kb_categories_tool_impl,  # Use passed function
            ListKBCategoriesParams,
            Dict[str, Any],  # Expects dict
            "List categories in a knowledge base",
            "raw_dict",  # Tool returns raw dict
        ),
        # User Management Tools
        "create_user": (
            create_user_tool,
            CreateUserParams,
            Dict[str, Any],  # Expects dict
            "Create a new user in ServiceNow",
            "raw_dict",  # Tool returns raw dict
        ),
        "update_user": (
            update_user_tool,
            UpdateUserParams,
            Dict[str, Any],  # Expects dict
            "Update an existing user in ServiceNow",
            "raw_dict",
        ),
        "get_user": (
            get_user_tool,
            GetUserParams,
            Dict[str, Any],  # Expects dict
            "Get a specific user in ServiceNow",
            "raw_dict",
        ),
        "list_users": (
            list_users_tool,
            ListUsersParams,
            Dict[str, Any],  # Expects dict
            "List users in ServiceNow",
            "raw_dict",
        ),
        "create_group": (
            create_group_tool,
            CreateGroupParams,
            Dict[str, Any],  # Expects dict
            "Create a new group in ServiceNow",
            "raw_dict",
        ),
        "update_group": (
            update_group_tool,
            UpdateGroupParams,
            Dict[str, Any],  # Expects dict
            "Update an existing group in ServiceNow",
            "raw_dict",
        ),
        "add_group_members": (
            add_group_members_tool,
            AddGroupMembersParams,
            Dict[str, Any],  # Expects dict
            "Add members to an existing group in ServiceNow",
            "raw_dict",
        ),
        "remove_group_members": (
            remove_group_members_tool,
            RemoveGroupMembersParams,
            Dict[str, Any],  # Expects dict
            "Remove members from an existing group in ServiceNow",
            "raw_dict",
        ),
        "list_groups": (
            list_groups_tool,
            ListGroupsParams,
            Dict[str, Any],  # Expects dict
            "List groups from ServiceNow with optional filtering",
            "raw_dict",
        ),
        # Story Management Tools
        "create_story": (
            create_story_tool,
            CreateStoryParams,
            str,
            "Create a new story in ServiceNow",
            "str",
        ),
        "update_story": (
            update_story_tool,
            UpdateStoryParams,
            str,
            "Update an existing story in ServiceNow",
            "str",
        ),
        "list_stories": (
            list_stories_tool,
            ListStoriesParams,
            str,  # Expects JSON string
            "List stories from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "list_story_dependencies": (
            list_story_dependencies_tool,
            ListStoryDependenciesParams,
            str,  # Expects JSON string
            "List story dependencies from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        "create_story_dependency": (
            create_story_dependency_tool,
            CreateStoryDependencyParams,
            str,
            "Create a dependency between two stories in ServiceNow",
            "str",
        ),
        "delete_story_dependency": (
            delete_story_dependency_tool,
            DeleteStoryDependencyParams,
            str,
            "Delete a story dependency in ServiceNow",
            "str",
        ),
        # Epic Management Tools
        "create_epic": (
            create_epic_tool,
            CreateEpicParams,
            str,
            "Create a new epic in ServiceNow",
            "str",
        ),
        "update_epic": (
            update_epic_tool,
            UpdateEpicParams,
            str,
            "Update an existing epic in ServiceNow",
            "str",
        ),
        "list_epics": (
            list_epics_tool,
            ListEpicsParams,
            str,  # Expects JSON string
            "List epics from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        # Scrum Task Management Tools
        "create_scrum_task": (
            create_scrum_task_tool,
            CreateScrumTaskParams,
            str,
            "Create a new scrum task in ServiceNow",
            "str",
        ),
        "update_scrum_task": (
            update_scrum_task_tool,
            UpdateScrumTaskParams,
            str,
            "Update an existing scrum task in ServiceNow",
            "str",
        ),
        "list_scrum_tasks": (
            list_scrum_tasks_tool,
            ListScrumTasksParams,
            str,  # Expects JSON string
            "List scrum tasks from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        # Project Management Tools
        "create_project": (
            create_project_tool,
            CreateProjectParams,
            str,
            "Create a new project in ServiceNow",
            "str",
        ),
        "update_project": (
            update_project_tool,
            UpdateProjectParams,
            str,
            "Update an existing project in ServiceNow",
            "str",
        ),
        "list_projects": (
            list_projects_tool,
            ListProjectsParams,
            str,  # Expects JSON string
            "List projects from ServiceNow",
            "json",  # Tool returns list/dict
        ),
        # Service Catalog Task (SCTASK) Tools
        "get_sctask": (
            get_sctask_tool,
            GetSCTaskParams,
            str,
            "Get a Service Catalog Task (SCTASK) by number from ServiceNow",
            "json",
        ),
        "list_sctasks": (
            list_sctasks_tool,
            ListSCTasksParams,
            str,
            "List Service Catalog Tasks (SCTASKs) from ServiceNow",
            "json",
        ),
        "update_sctask": (
            update_sctask_tool,
            UpdateSCTaskParams,
            str,
            "Update a Service Catalog Task (SCTASK) in ServiceNow",
            "json",
        ),
        # Time Card Tools
        "list_time_cards": (
            list_time_cards_tool,
            ListTimeCardsParams,
            str,
            "List time cards from ServiceNow, optionally filtered by task or user",
            "json",
        ),
        "create_time_card": (
            create_time_card_tool,
            CreateTimeCardParams,
            str,
            "Create a new time card entry for a task in ServiceNow",
            "json",
        ),
        "update_time_card": (
            update_time_card_tool,
            UpdateTimeCardParams,
            str,
            "Update an existing time card entry in ServiceNow",
            "json",
        ),
        # Syslog Tools
        "list_syslog_entries": (
            list_syslog_entries_tool,
            ListSyslogEntriesParams,
            str,
            "List syslog entries from ServiceNow, with optional filters for level, source, and date range",
            "json",
        ),
        "get_syslog_entry": (
            get_syslog_entry_tool,
            GetSyslogEntryParams,
            str,
            "Retrieve a single syslog entry by its sys_id",
            "json",
        ),
        # UI Policy Tools
        "create_ui_policy": (
            create_ui_policy_tool,
            CreateUIPolicyParams,
            Dict[str, Any],
            "Create a UI policy that controls field behaviour (mandatory/visible/read-only) on a ServiceNow form",
            "dict",
        ),
        "create_ui_policy_action": (
            create_ui_policy_action_tool,
            CreateUIPolicyActionParams,
            Dict[str, Any],
            "Create a UI policy action that sets the mandatory/visible/read-only state of a form field when a UI policy condition fires",
            "dict",
        ),
        # User Criteria Tools
        "create_user_criteria": (
            create_user_criteria_tool,
            CreateUserCriteriaParams,
            Dict[str, Any],
            "Create a User Criteria record that controls who can see or request Service Catalog items based on role, group, department, company, location, or a custom script",
            "dict",
        ),
        "create_user_criteria_condition": (
            create_user_criteria_condition_tool,
            CreateUserCriteriaConditionParams,
            Dict[str, Any],
            "Apply a User Criteria record to a Service Catalog entity (item, category, or catalog) to grant or deny access for matching users",
            "dict",
        ),
        # Bulk Operations
        "execute_bulk_operations": (
            execute_bulk_operations_tool,
            BulkOperationsParams,
            Dict[str, Any],
            (
                "Execute up to 100 ServiceNow API calls in a single HTTP round-trip "
                "using the ServiceNow Batch API. Each request specifies a method, "
                "relative URL path, and optional body. Results are returned in the "
                "same order with per-request status codes and parsed response bodies."
            ),
            "raw_dict",
        ),
        # CMDB Tools
        "list_cis": (
            list_cis_tool,
            ListCIsParams,
            Dict[str, Any],
            (
                "List CMDB configuration items (CIs) from ServiceNow with optional "
                "filters for CI class, name, operational status, and environment. "
                "Supports pagination."
            ),
            "raw_dict",
        ),
        "get_ci": (
            get_ci_tool,
            GetCIParams,
            Dict[str, Any],
            "Retrieve a single CMDB configuration item by its sys_id",
            "raw_dict",
        ),
        "create_ci": (
            create_ci_tool,
            CreateCIParams,
            Dict[str, Any],
            (
                "Create a new CMDB configuration item. Specify ci_class to create "
                "in a specific class table (e.g. cmdb_ci_server). Defaults to the "
                "base cmdb_ci table."
            ),
            "raw_dict",
        ),
        "update_ci": (
            update_ci_tool,
            UpdateCIParams,
            Dict[str, Any],
            "Update an existing CMDB configuration item by its sys_id",
            "raw_dict",
        ),
        # CMDB Relationship Tools
        "list_ci_relationships": (
            list_ci_relationships_tool,
            ListCIRelationshipsParams,
            Dict[str, Any],
            (
                "List CI relationships from the cmdb_rel_ci table with optional "
                "filters for parent CI, child CI, and relationship type. Supports pagination."
            ),
            "raw_dict",
        ),
        "get_ci_relationship": (
            get_ci_relationship_tool,
            GetCIRelationshipParams,
            Dict[str, Any],
            "Retrieve a single CI relationship record by its sys_id",
            "raw_dict",
        ),
        "create_ci_relationship": (
            create_ci_relationship_tool,
            CreateCIRelationshipParams,
            Dict[str, Any],
            (
                "Create a directional relationship between two CIs in the CMDB. "
                "Requires the sys_id of the parent CI, child CI, and the desired "
                "cmdb_rel_type (use list_ci_relationship_types to find the type sys_id)."
            ),
            "raw_dict",
        ),
        "delete_ci_relationship": (
            delete_ci_relationship_tool,
            DeleteCIRelationshipParams,
            Dict[str, Any],
            "Delete a CI relationship record from the cmdb_rel_ci table by its sys_id",
            "raw_dict",
        ),
        "list_ci_relationship_types": (
            list_ci_relationship_types_tool,
            ListCIRelationshipTypesParams,
            Dict[str, Any],
            (
                "List available CI relationship types from the cmdb_rel_type table. "
                "Each type has a parent_descriptor (e.g. 'Depends on') and a "
                "child_descriptor (e.g. 'Used by'). Filter by name substring."
            ),
            "raw_dict",
        ),
        # Asset Management Tools
        "create_asset": (
            create_asset_tool,
            CreateAssetParams,
            Dict[str, Any],
            (
                "Create a new asset record in the ServiceNow alm_asset table or a subclass "
                "such as alm_hardware. For hardware assets supply asset_class='alm_hardware' "
                "and optionally include CPU, RAM, disk, OS, and network fields."
            ),
            "raw_dict",
        ),
        "list_assets": (
            list_assets_tool,
            ListAssetsParams,
            Dict[str, Any],
            (
                "List hardware and software assets from the ServiceNow alm_asset table "
                "with optional filters for asset tag, display name, install status, "
                "assigned user, and model category. Supports pagination."
            ),
            "raw_dict",
        ),
        "get_asset": (
            get_asset_tool,
            GetAssetParams,
            Dict[str, Any],
            (
                "Retrieve a single asset record from the alm_asset table. "
                "Lookup by sys_id or by asset tag."
            ),
            "raw_dict",
        ),
        "update_asset": (
            update_asset_tool,
            UpdateAssetParams,
            Dict[str, Any],
            (
                "Update an existing asset record in the alm_asset table. "
                "Supports updating status, cost, dates, assignment, and location fields."
            ),
            "raw_dict",
        ),
        "delete_asset": (
            delete_asset_tool,
            DeleteAssetParams,
            Dict[str, Any],
            (
                "Permanently delete an asset record from the alm_asset table by its sys_id. "
                "This action is irreversible — confirm the sys_id before calling."
            ),
            "raw_dict",
        ),
        # Contract Management Tools
        "list_asset_contracts": (
            list_asset_contracts_tool,
            ListAssetContractsParams,
            Dict[str, Any],
            (
                "List asset contracts from the ServiceNow alm_contract table with optional "
                "filters for vendor, state, contract type, description, and date ranges. "
                "Supports pagination."
            ),
            "raw_dict",
        ),
        "get_asset_contract": (
            get_asset_contract_tool,
            GetAssetContractParams,
            Dict[str, Any],
            (
                "Retrieve a single asset contract from the alm_contract table. "
                "Lookup by sys_id or by contract number (e.g. CON0001234)."
            ),
            "raw_dict",
        ),
        "create_asset_contract": (
            create_asset_contract_tool,
            CreateAssetContractParams,
            Dict[str, Any],
            (
                "Create a new contract record in the alm_contract table. "
                "Requires a short_description; optionally accepts vendor, dates, "
                "value, currency, type, category, state, and assignment fields."
            ),
            "raw_dict",
        ),
        "update_asset_contract": (
            update_asset_contract_tool,
            UpdateAssetContractParams,
            Dict[str, Any],
            (
                "Update an existing contract in the alm_contract table by sys_id. "
                "Supply only the fields that need to change."
            ),
            "raw_dict",
        ),
        "list_contract_assets": (
            list_contract_assets_tool,
            ListContractAssetsParams,
            Dict[str, Any],
            (
                "List alm_asset records linked to a specific contract via the "
                "maintenance_contract field. Requires contract_sys_id; optionally filter "
                "by install_status or display_name. Supports pagination."
            ),
            "raw_dict",
        ),
        "expire_asset_contract": (
            expire_asset_contract_tool,
            ExpireAssetContractParams,
            Dict[str, Any],
            (
                "Transition an alm_contract record to the 'expired' state. "
                "Requires sys_id; optionally accepts notes to record alongside "
                "the state change."
            ),
            "raw_dict",
        ),
        # Attachment Tools
        "list_attachments": (
            list_attachments_tool,
            ListAttachmentsParams,
            Dict[str, Any],
            (
                "List file attachments for a ServiceNow record. Requires table_name "
                "(e.g. 'incident') and table_sys_id; optionally filter by file_name "
                "or content_type. Supports pagination."
            ),
            "raw_dict",
        ),
        "get_attachment": (
            get_attachment_tool,
            GetAttachmentParams,
            Dict[str, Any],
            "Get metadata for a specific attachment by its sys_id.",
            "raw_dict",
        ),
        "delete_attachment": (
            delete_attachment_tool,
            DeleteAttachmentParams,
            Dict[str, Any],
            "Permanently delete a file attachment from ServiceNow by its sys_id.",
            "raw_dict",
        ),
    }
    return tool_definitions
