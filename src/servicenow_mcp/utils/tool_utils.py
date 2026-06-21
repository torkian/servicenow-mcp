from typing import Any, Callable, Dict, Tuple, Type

from servicenow_mcp.tools.asset_tools import (
    CreateAssetParams,
    DeleteAssetParams,
    GetAssetParams,
    ListAssetsParams,
    UpdateAssetParams,
)
from servicenow_mcp.tools.asset_tools import (
    create_asset as create_asset_tool,
)
from servicenow_mcp.tools.asset_tools import (
    delete_asset as delete_asset_tool,
)
from servicenow_mcp.tools.asset_tools import (
    get_asset as get_asset_tool,
)
from servicenow_mcp.tools.asset_tools import (
    list_assets as list_assets_tool,
)
from servicenow_mcp.tools.asset_tools import (
    update_asset as update_asset_tool,
)
from servicenow_mcp.tools.attachment_tools import (
    DeleteAttachmentParams,
    GetAttachmentParams,
    ListAttachmentsParams,
)
from servicenow_mcp.tools.attachment_tools import (
    delete_attachment as delete_attachment_tool,
)
from servicenow_mcp.tools.attachment_tools import (
    get_attachment as get_attachment_tool,
)
from servicenow_mcp.tools.attachment_tools import (
    list_attachments as list_attachments_tool,
)
from servicenow_mcp.tools.bulk_tools import (
    BulkOperationsParams,
    BulkUpdateChangeRequestsParams,
    BulkUpdateChangeTasksParams,
    BulkUpdateIncidentsParams,
    BulkUpdateProblemsParams,
)
from servicenow_mcp.tools.bulk_tools import (
    bulk_update_change_requests as bulk_update_change_requests_tool,
)
from servicenow_mcp.tools.bulk_tools import (
    bulk_update_change_tasks as bulk_update_change_tasks_tool,
)
from servicenow_mcp.tools.bulk_tools import (
    bulk_update_incidents as bulk_update_incidents_tool,
)
from servicenow_mcp.tools.bulk_tools import (
    bulk_update_problems as bulk_update_problems_tool,
)
from servicenow_mcp.tools.bulk_tools import (
    execute_bulk_operations as execute_bulk_operations_tool,
)

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
    GetCatalogParams,
    ListCatalogCategoriesParams,
    ListCatalogItemsParams,
    ListCatalogsParams,
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
    get_catalog as get_catalog_tool,
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
    list_catalogs as list_catalogs_tool,
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
    ApproveChangeApprovalParams,
    ApproveChangeParams,
    CancelChangeRequestParams,
    CloseChangeTaskParams,
    CreateChangeRequestParams,
    CreateChangeTaskParams,
    GetChangeApprovalParams,
    GetChangeRequestDetailsParams,
    GetChangeTaskParams,
    ListChangeApprovalsParams,
    ListChangeRequestsParams,
    ListChangeRiskAssessmentsParams,
    ListChangeTasksParams,
    RejectChangeApprovalParams,
    RejectChangeParams,
    ReopenChangeRequestParams,
    SubmitChangeForApprovalParams,
    UpdateChangeRequestParams,
    UpdateChangeTaskParams,
)
from servicenow_mcp.tools.change_tools import (
    add_change_task as add_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    approve_change as approve_change_tool,
)
from servicenow_mcp.tools.change_tools import (
    approve_change_approval as approve_change_approval_tool,
)
from servicenow_mcp.tools.change_tools import (
    reject_change_approval as reject_change_approval_tool,
)
from servicenow_mcp.tools.change_tools import (
    get_change_approval as get_change_approval_tool,
)
from servicenow_mcp.tools.change_tools import (
    get_change_task as get_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    cancel_change_request as cancel_change_request_tool,
)
from servicenow_mcp.tools.change_tools import (
    create_change_request as create_change_request_tool,
)
from servicenow_mcp.tools.change_tools import (
    create_change_task as create_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    get_change_request_details as get_change_request_details_tool,
)
from servicenow_mcp.tools.change_tools import (
    list_change_approvals as list_change_approvals_tool,
)
from servicenow_mcp.tools.change_tools import (
    list_change_requests as list_change_requests_tool,
)
from servicenow_mcp.tools.change_tools import (
    list_change_tasks as list_change_tasks_tool,
)
from servicenow_mcp.tools.change_tools import (
    reject_change as reject_change_tool,
)
from servicenow_mcp.tools.change_tools import (
    reopen_change_request as reopen_change_request_tool,
)
from servicenow_mcp.tools.change_tools import (
    submit_change_for_approval as submit_change_for_approval_tool,
)
from servicenow_mcp.tools.change_tools import (
    update_change_request as update_change_request_tool,
)
from servicenow_mcp.tools.change_tools import (
    update_change_task as update_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    close_change_task as close_change_task_tool,
)
from servicenow_mcp.tools.change_tools import (
    list_change_risk_assessments as list_change_risk_assessments_tool,
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
from servicenow_mcp.tools.cmdb_relationship_tools import (
    CreateCIRelationshipParams,
    DeleteCIRelationshipParams,
    GetCIRelationshipParams,
    ListCIRelationshipsParams,
    ListCIRelationshipTypesParams,
)
from servicenow_mcp.tools.cmdb_relationship_tools import (
    create_ci_relationship as create_ci_relationship_tool,
)
from servicenow_mcp.tools.cmdb_relationship_tools import (
    delete_ci_relationship as delete_ci_relationship_tool,
)
from servicenow_mcp.tools.cmdb_relationship_tools import (
    get_ci_relationship as get_ci_relationship_tool,
)
from servicenow_mcp.tools.cmdb_relationship_tools import (
    list_ci_relationship_types as list_ci_relationship_types_tool,
)
from servicenow_mcp.tools.cmdb_relationship_tools import (
    list_ci_relationships as list_ci_relationships_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    CreateCIOutageParams,
    CreateCIParams,
    DeleteCIOutageParams,
    GetCIByNameParams,
    GetCIOutageParams,
    GetCIParams,
    ListCIsParams,
    ListCMDBCIOutagesParams,
    ListCMDBClassesParams,
    UpdateCIOutageParams,
    UpdateCIParams,
)
from servicenow_mcp.tools.cmdb_tools import (
    create_ci as create_ci_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    create_ci_outage as create_ci_outage_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    delete_ci_outage as delete_ci_outage_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    get_ci as get_ci_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    get_ci_by_name as get_ci_by_name_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    get_ci_outage as get_ci_outage_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    list_cis as list_cis_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    list_cmdb_ci_outages as list_cmdb_ci_outages_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    list_cmdb_classes as list_cmdb_classes_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    update_ci as update_ci_tool,
)
from servicenow_mcp.tools.cmdb_tools import (
    update_ci_outage as update_ci_outage_tool,
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
)
from servicenow_mcp.tools.contract_tools import (
    expire_asset_contract as expire_asset_contract_tool,
)
from servicenow_mcp.tools.contract_tools import (
    get_asset_contract as get_asset_contract_tool,
)
from servicenow_mcp.tools.contract_tools import (
    list_asset_contracts as list_asset_contracts_tool,
)
from servicenow_mcp.tools.contract_tools import (
    list_contract_assets as list_contract_assets_tool,
)
from servicenow_mcp.tools.contract_tools import (
    update_asset_contract as update_asset_contract_tool,
)
from servicenow_mcp.tools.epic_tools import (
    CreateEpicParams,
    ListEpicsParams,
    UpdateEpicParams,
)
from servicenow_mcp.tools.epic_tools import (
    create_epic as create_epic_tool,
)
from servicenow_mcp.tools.epic_tools import (
    list_epics as list_epics_tool,
)
from servicenow_mcp.tools.epic_tools import (
    update_epic as update_epic_tool,
)
from servicenow_mcp.tools.incident_task_tools import (
    CloseIncidentTaskParams,
    CreateIncidentTaskParams,
    ListIncidentCommentsParams,
    ListIncidentTasksParams,
)
from servicenow_mcp.tools.incident_task_tools import (
    close_incident_task as close_incident_task_tool,
)
from servicenow_mcp.tools.incident_task_tools import (
    create_incident_task as create_incident_task_tool,
)
from servicenow_mcp.tools.incident_task_tools import (
    list_incident_comments as list_incident_comments_tool,
)
from servicenow_mcp.tools.incident_task_tools import (
    list_incident_tasks as list_incident_tasks_tool,
)
from servicenow_mcp.tools.incident_tools import (
    AddCommentParams,
    CreateIncidentParams,
    DeleteIncidentParams,
    EscalateIncidentParams,
    GetIncidentByNumberParams,
    ListIncidentsParams,
    ReopenIncidentParams,
    ResolveIncidentParams,
    UpdateIncidentParams,
)
from servicenow_mcp.tools.incident_tools import (
    add_comment as add_comment_tool,
)
from servicenow_mcp.tools.incident_tools import (
    create_incident as create_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    delete_incident as delete_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    escalate_incident as escalate_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    get_incident_by_number as get_incident_by_number_tool,
)
from servicenow_mcp.tools.incident_tools import (
    list_incidents as list_incidents_tool,
)
from servicenow_mcp.tools.incident_tools import (
    reopen_incident as reopen_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    resolve_incident as resolve_incident_tool,
)
from servicenow_mcp.tools.incident_tools import (
    update_incident as update_incident_tool,
)
from servicenow_mcp.tools.knowledge_base import (
    CreateArticleParams,
    CreateKnowledgeArticleParams,
    CreateKnowledgeBaseParams,
    GetArticleParams,
    ListArticlesByCategoryParams,
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
    create_knowledge_article as create_knowledge_article_tool,
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
    list_articles_by_category as list_articles_by_category_tool,
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
from servicenow_mcp.tools.notification_tools import (
    ListNotificationsParams,
)
from servicenow_mcp.tools.notification_tools import (
    list_notifications as list_notifications_tool,
)
from servicenow_mcp.tools.problem_tools import (
    CloseProblemParams,
    CreateProblemParams,
    GetProblemParams,
    ListProblemsParams,
    UpdateProblemParams,
)
from servicenow_mcp.tools.problem_tools import (
    close_problem as close_problem_tool,
)
from servicenow_mcp.tools.problem_tools import (
    create_problem as create_problem_tool,
)
from servicenow_mcp.tools.problem_tools import (
    get_problem as get_problem_tool,
)
from servicenow_mcp.tools.problem_tools import (
    list_problems as list_problems_tool,
)
from servicenow_mcp.tools.problem_tools import (
    update_problem as update_problem_tool,
)
from servicenow_mcp.tools.project_tools import (
    CreateProjectParams,
    ListProjectsParams,
    UpdateProjectParams,
)
from servicenow_mcp.tools.project_tools import (
    create_project as create_project_tool,
)
from servicenow_mcp.tools.project_tools import (
    list_projects as list_projects_tool,
)
from servicenow_mcp.tools.project_tools import (
    update_project as update_project_tool,
)
from servicenow_mcp.tools.request_tools import (
    CreateRequestParams,
    GetRequestParams,
    ListRequestItemsParams,
    ListRequestsParams,
    UpdateRequestParams,
)
from servicenow_mcp.tools.request_tools import (
    create_request as create_request_tool,
)
from servicenow_mcp.tools.request_tools import (
    get_request as get_request_tool,
)
from servicenow_mcp.tools.request_tools import (
    list_request_items as list_request_items_tool,
)
from servicenow_mcp.tools.request_tools import (
    list_requests as list_requests_tool,
)
from servicenow_mcp.tools.request_tools import (
    update_request as update_request_tool,
)
from servicenow_mcp.tools.role_tools import (
    AssignRoleToGroupParams,
    GetGroupRolesParams,
    ListUserRolesParams,
    RemoveRoleFromGroupParams,
)
from servicenow_mcp.tools.role_tools import (
    assign_role_to_group as assign_role_to_group_tool,
)
from servicenow_mcp.tools.role_tools import (
    get_group_roles as get_group_roles_tool,
)
from servicenow_mcp.tools.role_tools import (
    list_user_roles as list_user_roles_tool,
)
from servicenow_mcp.tools.role_tools import (
    remove_role_from_group as remove_role_from_group_tool,
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
from servicenow_mcp.tools.scrum_task_tools import (
    CreateScrumTaskParams,
    ListScrumTasksParams,
    UpdateScrumTaskParams,
)
from servicenow_mcp.tools.scrum_task_tools import (
    create_scrum_task as create_scrum_task_tool,
)
from servicenow_mcp.tools.scrum_task_tools import (
    list_scrum_tasks as list_scrum_tasks_tool,
)
from servicenow_mcp.tools.scrum_task_tools import (
    update_scrum_task as update_scrum_task_tool,
)
from servicenow_mcp.tools.sctask_tools import (
    GetSCTaskParams,
    ListSCTasksParams,
    UpdateSCTaskParams,
)
from servicenow_mcp.tools.sctask_tools import (
    get_sctask as get_sctask_tool,
)
from servicenow_mcp.tools.sctask_tools import (
    list_sctasks as list_sctasks_tool,
)
from servicenow_mcp.tools.sctask_tools import (
    update_sctask as update_sctask_tool,
)
from servicenow_mcp.tools.sla_tools import (
    GetSLABreachParams,
    GetSLAParams,
    ListSLABreachDefinitionsParams,
    ListSLABreachesParams,
    ListSLAsParams,
    ResolveSLABreachParams,
)
from servicenow_mcp.tools.sla_tools import (
    get_sla as get_sla_tool,
)
from servicenow_mcp.tools.sla_tools import (
    get_sla_breach as get_sla_breach_tool,
)
from servicenow_mcp.tools.sla_tools import (
    list_sla_breach_definitions as list_sla_breach_definitions_tool,
)
from servicenow_mcp.tools.sla_tools import (
    list_sla_breaches as list_sla_breaches_tool,
)
from servicenow_mcp.tools.sla_tools import (
    list_slas as list_slas_tool,
)
from servicenow_mcp.tools.sla_tools import (
    resolve_sla_breach as resolve_sla_breach_tool,
)
from servicenow_mcp.tools.story_tools import (
    CreateStoryDependencyParams,
    CreateStoryParams,
    DeleteStoryDependencyParams,
    ListStoriesParams,
    ListStoryDependenciesParams,
    UpdateStoryParams,
)
from servicenow_mcp.tools.story_tools import (
    create_story as create_story_tool,
)
from servicenow_mcp.tools.story_tools import (
    create_story_dependency as create_story_dependency_tool,
)
from servicenow_mcp.tools.story_tools import (
    delete_story_dependency as delete_story_dependency_tool,
)
from servicenow_mcp.tools.story_tools import (
    list_stories as list_stories_tool,
)
from servicenow_mcp.tools.story_tools import (
    list_story_dependencies as list_story_dependencies_tool,
)
from servicenow_mcp.tools.story_tools import (
    update_story as update_story_tool,
)
from servicenow_mcp.tools.syslog_tools import (
    GetSyslogEntryParams,
    ListSyslogEntriesParams,
)
from servicenow_mcp.tools.syslog_tools import (
    get_syslog_entry as get_syslog_entry_tool,
)
from servicenow_mcp.tools.syslog_tools import (
    list_syslog_entries as list_syslog_entries_tool,
)
from servicenow_mcp.tools.time_card_tools import (
    CreateTimeCardParams,
    ListTimeCardsParams,
    UpdateTimeCardParams,
)
from servicenow_mcp.tools.time_card_tools import (
    create_time_card as create_time_card_tool,
)
from servicenow_mcp.tools.time_card_tools import (
    list_time_cards as list_time_cards_tool,
)
from servicenow_mcp.tools.time_card_tools import (
    update_time_card as update_time_card_tool,
)
from servicenow_mcp.tools.ui_policy_tools import (
    CreateUIPolicyActionParams,
    CreateUIPolicyParams,
)
from servicenow_mcp.tools.ui_policy_tools import (
    create_ui_policy as create_ui_policy_tool,
)
from servicenow_mcp.tools.ui_policy_tools import (
    create_ui_policy_action as create_ui_policy_action_tool,
)
from servicenow_mcp.tools.user_criteria_tools import (
    CreateUserCriteriaConditionParams,
    CreateUserCriteriaParams,
    ListCatalogItemUserCriteriaParams,
)
from servicenow_mcp.tools.user_criteria_tools import (
    create_user_criteria as create_user_criteria_tool,
)
from servicenow_mcp.tools.user_criteria_tools import (
    create_user_criteria_condition as create_user_criteria_condition_tool,
)
from servicenow_mcp.tools.user_criteria_tools import (
    list_catalog_item_user_criteria as list_catalog_item_user_criteria_tool,
)
from servicenow_mcp.tools.user_group_tools import (
    AddUserToGroupParams,
    GetUserGroupParams,
    ListGroupMembersParams,
    ListUserGroupsParams,
    RemoveUserFromGroupParams,
)
from servicenow_mcp.tools.user_group_tools import (
    add_user_to_group as add_user_to_group_tool,
)
from servicenow_mcp.tools.user_group_tools import (
    get_user_group as get_user_group_tool,
)
from servicenow_mcp.tools.user_group_tools import (
    list_group_members as list_group_members_tool,
)
from servicenow_mcp.tools.user_group_tools import (
    list_user_groups as list_user_groups_tool,
)
from servicenow_mcp.tools.user_group_tools import (
    remove_user_from_group as remove_user_from_group_tool,
)
from servicenow_mcp.tools.user_tools import (
    AddGroupMembersParams,
    CreateGroupParams,
    CreateUserParams,
    GetUserByEmailParams,
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
    get_user_by_email as get_user_by_email_tool,
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
        "delete_incident": (
            delete_incident_tool,
            DeleteIncidentParams,
            str,
            (
                "Permanently delete an incident record from ServiceNow by incident number or sys_id. "
                "This action is irreversible — confirm the incident ID before calling."
            ),
            "str",
        ),
        "reopen_incident": (
            reopen_incident_tool,
            ReopenIncidentParams,
            str,
            "Reopen a resolved or closed incident, setting its state back to New or In Progress",
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
        "escalate_incident": (
            escalate_incident_tool,
            EscalateIncidentParams,
            str,
            (
                "Escalate a ServiceNow incident by updating its priority and optionally reassigning "
                "it to a different group. Accepts an incident number (e.g. INC0010001) or sys_id. "
                "A required priority value ('1'=Critical … '5'=Planning) is set via PATCH. "
                "Optionally supply assignment_group to reassign and audit_note to document the reason."
            ),
            "str",
        ),
        # Incident Task Tools
        "create_incident_task": (
            create_incident_task_tool,
            CreateIncidentTaskParams,
            str,
            "Create a task (sc_task) linked to a specific incident in ServiceNow",
            "json",
        ),
        "list_incident_tasks": (
            list_incident_tasks_tool,
            ListIncidentTasksParams,
            str,
            "List tasks (sc_task) linked to a specific incident in ServiceNow",
            "json",
        ),
        "list_incident_comments": (
            list_incident_comments_tool,
            ListIncidentCommentsParams,
            str,
            "List journal entries (comments and work notes) for an incident in ServiceNow",
            "json",
        ),
        "close_incident_task": (
            close_incident_task_tool,
            CloseIncidentTaskParams,
            Dict[str, Any],
            (
                "Close an incident task (sc_task) by setting its state to Closed Complete (3). "
                "Accepts an sc_task number (e.g. TASK0010001) or sys_id. "
                "Optionally include close_notes and work_notes."
            ),
            "raw_dict",
        ),
        # Catalog Tools
        "list_catalogs": (
            list_catalogs_tool,
            ListCatalogsParams,
            str,
            "List service catalogs (sc_catalog table).",
            "json",
        ),
        "get_catalog": (
            get_catalog_tool,
            GetCatalogParams,
            str,
            "Get a specific service catalog by sys_id.",
            "json_dict",
        ),
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
        "get_change_task": (
            get_change_task_tool,
            GetChangeTaskParams,
            str,
            "Get a single change task by its sys_id or CTASK number",
            "json",
        ),
        "list_change_tasks": (
            list_change_tasks_tool,
            ListChangeTasksParams,
            str,
            "List tasks linked to a specific change request in ServiceNow",
            "json",
        ),
        "create_change_task": (
            create_change_task_tool,
            CreateChangeTaskParams,
            str,
            "Create a task linked to a specific change request in ServiceNow",
            "json",
        ),
        "update_change_task": (
            update_change_task_tool,
            UpdateChangeTaskParams,
            str,
            "Update an existing change task (state, assignee, dates, notes)",
            "json",
        ),
        "close_change_task": (
            close_change_task_tool,
            CloseChangeTaskParams,
            str,
            "Close a change task by setting its state to Closed Complete (or Closed Incomplete/Skipped)",
            "json",
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
        "cancel_change_request": (
            cancel_change_request_tool,
            CancelChangeRequestParams,
            str,
            "Cancel a change request",
            "json",
        ),
        "reopen_change_request": (
            reopen_change_request_tool,
            ReopenChangeRequestParams,
            str,
            "Reopen a cancelled or closed change request",
            "json",
        ),
        "list_change_approvals": (
            list_change_approvals_tool,
            ListChangeApprovalsParams,
            str,
            (
                "List approval records for change requests from the "
                "sysapproval_approver table. Scoped to source_table=change_request. "
                "Filter by change_id (CHG number or sys_id), state "
                "(requested/approved/rejected/not_yet_requested/cancelled), "
                "or approver user name. Returns approvals list with pagination."
            ),
            "json",
        ),
        "get_change_approval": (
            get_change_approval_tool,
            GetChangeApprovalParams,
            str,
            (
                "Retrieve a single sysapproval_approver record by its sys_id. "
                "Returns normalised approval fields: change_request, approver, "
                "state, comments, due_date, created_on, updated_on. "
                "Returns 404 guard when the record does not exist."
            ),
            "json",
        ),
        "approve_change_approval": (
            approve_change_approval_tool,
            ApproveChangeApprovalParams,
            str,
            (
                "Approve a specific sysapproval_approver record directly by its sys_id. "
                "Sets state=approved and optionally records comments. "
                "Use list_change_approvals or get_change_approval to obtain the sys_id first. "
                "Returns 404 guard when the record does not exist."
            ),
            "json",
        ),
        "reject_change_approval": (
            reject_change_approval_tool,
            RejectChangeApprovalParams,
            str,
            (
                "Reject a specific sysapproval_approver record directly by its sys_id. "
                "Sets state=rejected and records the required rejection_reason as comments. "
                "Use list_change_approvals or get_change_approval to obtain the sys_id first. "
                "Returns 404 guard when the record does not exist."
            ),
            "json",
        ),
        "list_change_risk_assessments": (
            list_change_risk_assessments_tool,
            ListChangeRiskAssessmentsParams,
            str,
            (
                "List risk_assessment records scoped to change requests "
                "(source_table=change_request). Optionally filter by a specific "
                "change request (CHG number or sys_id) and by assessment state "
                "(draft/pending/complete). Returns assessments list with pagination "
                "(has_more/next_offset)."
            ),
            "json",
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
        "create_knowledge_article": (
            create_knowledge_article_tool,
            CreateKnowledgeArticleParams,
            str,
            (
                "Create a knowledge article, automatically resolving knowledge base and category "
                "by name or sys_id. Supports extra fields: author, expiry date (valid_to), "
                "flagged status, commenting and suggesting controls, and optional immediate publish."
            ),
            "json_dict",
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
        "list_articles_by_category": (
            list_articles_by_category_tool,
            ListArticlesByCategoryParams,
            Dict[str, Any],
            (
                "List knowledge articles within a specific category. "
                "Accepts category name or sys_id; resolves name to sys_id automatically. "
                "Returns richer metadata (author, view_count, keywords) than list_articles."
            ),
            "raw_dict",
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
        "get_user_by_email": (
            get_user_by_email_tool,
            GetUserByEmailParams,
            Dict[str, Any],
            "Look up a ServiceNow user by email address (exact or partial match)",
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
        "list_catalog_item_user_criteria": (
            list_catalog_item_user_criteria_tool,
            ListCatalogItemUserCriteriaParams,
            Dict[str, Any],
            (
                "List catalog item visibility rules from the ServiceNow user criteria "
                "junction tables. Query sc_cat_item_user_criteria_mtom (allow-list) or "
                "sc_cat_item_user_criteria_no_mtom (deny-list) by setting visibility to "
                "'can_see' or 'cannot_see'. Filter by catalog_item_id or user_criteria_id. "
                "Supports pagination. Useful for auditing which user criteria control "
                "access to specific catalog items."
            ),
            "raw_dict",
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
        "bulk_update_incidents": (
            bulk_update_incidents_tool,
            BulkUpdateIncidentsParams,
            Dict[str, Any],
            (
                "PATCH multiple ServiceNow incidents in a single Batch API call. "
                "Each update entry specifies an incident_id (number or sys_id) and "
                "the fields to change (short_description, state, priority, assigned_to, "
                "work_notes, etc.). Incident numbers are resolved to sys_ids with one "
                "preliminary GET before the batch PATCH is issued. Up to 100 incidents "
                "per call. Returns per-incident ok/status_code with the original incident_id."
            ),
            "raw_dict",
        ),
        "bulk_update_change_requests": (
            bulk_update_change_requests_tool,
            BulkUpdateChangeRequestsParams,
            Dict[str, Any],
            (
                "PATCH multiple ServiceNow change requests in a single Batch API call. "
                "Each update entry specifies a change_id (CHG number or sys_id) and "
                "the fields to change (short_description, state, type, risk, impact, "
                "priority, assignment_group, start_date, end_date, work_notes, etc.). "
                "Change request numbers are resolved to sys_ids with one preliminary GET "
                "before the batch PATCH is issued. Up to 100 change requests per call. "
                "Returns per-change ok/status_code with the original change_id."
            ),
            "raw_dict",
        ),
        "bulk_update_problems": (
            bulk_update_problems_tool,
            BulkUpdateProblemsParams,
            Dict[str, Any],
            (
                "PATCH multiple ServiceNow problems in a single Batch API call. "
                "Each update entry specifies a problem_id (PRB number or sys_id) and "
                "the fields to change (short_description, state, priority, impact, urgency, "
                "assigned_to, assignment_group, known_error, cause_notes, fix_notes, "
                "work_notes, category). "
                "Problem numbers are resolved to sys_ids with one preliminary GET "
                "before the batch PATCH is issued. Up to 100 problems per call. "
                "Returns per-problem ok/status_code with the original problem_id."
            ),
            "raw_dict",
        ),
        "bulk_update_change_tasks": (
            bulk_update_change_tasks_tool,
            BulkUpdateChangeTasksParams,
            Dict[str, Any],
            (
                "PATCH multiple ServiceNow change tasks in a single Batch API call. "
                "Each update entry specifies a task_id (CTASK number or sys_id) and "
                "the fields to change (short_description, description, state, assigned_to, "
                "assignment_group, planned_start_date, planned_end_date, work_notes, close_notes). "
                "CTASK numbers are resolved to sys_ids with one preliminary GET "
                "before the batch PATCH is issued. Up to 100 tasks per call. "
                "Returns per-task ok/status_code with the original task_id."
            ),
            "raw_dict",
        ),
        # CMDB Tools
        "list_cmdb_classes": (
            list_cmdb_classes_tool,
            ListCMDBClassesParams,
            Dict[str, Any],
            (
                "Return a sorted list of distinct CI class names (sys_class_name) "
                "present in the CMDB, using the ServiceNow aggregate API. "
                "Optionally filter by a base class table or an encoded query, "
                "and include the record count per class."
            ),
            "raw_dict",
        ),
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
        "get_ci_by_name": (
            get_ci_by_name_tool,
            GetCIByNameParams,
            Dict[str, Any],
            (
                "Search for CMDB configuration items by name substring. Returns all CIs "
                "whose name contains the given string. Use exact=true for an exact match. "
                "Optionally scope the search to a specific ci_class table."
            ),
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
        "list_cmdb_ci_outages": (
            list_cmdb_ci_outages_tool,
            ListCMDBCIOutagesParams,
            Dict[str, Any],
            (
                "List CI outage records from the cmdb_ci_outage table. "
                "Filter by affected CI sys_id, outage type, resolved state, "
                "and begin date range. Supports pagination."
            ),
            "raw_dict",
        ),
        "get_ci_outage": (
            get_ci_outage_tool,
            GetCIOutageParams,
            Dict[str, Any],
            "Retrieve a single CMDB CI outage record by its sys_id",
            "raw_dict",
        ),
        "create_ci_outage": (
            create_ci_outage_tool,
            CreateCIOutageParams,
            Dict[str, Any],
            (
                "Create a new outage record in the cmdb_ci_outage table to mark a CI "
                "as impacted. Requires the affected CI sys_id and an outage begin datetime. "
                "Optionally specify type, end time, cause CI, resolved state, and resolution notes."
            ),
            "raw_dict",
        ),
        "update_ci_outage": (
            update_ci_outage_tool,
            UpdateCIOutageParams,
            Dict[str, Any],
            (
                "Update an existing CI outage record in the cmdb_ci_outage table. "
                "Requires the outage sys_id. Set end time and resolution_notes to document "
                "resolution, or set resolved=True to mark the outage as resolved. "
                "Only supplied fields are modified."
            ),
            "raw_dict",
        ),
        "delete_ci_outage": (
            delete_ci_outage_tool,
            DeleteCIOutageParams,
            Dict[str, Any],
            (
                "Permanently delete a CI outage record from the cmdb_ci_outage table by its sys_id. "
                "Returns success on 204 or 200, failure on 404."
            ),
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
        # Service Request Tools
        "list_requests": (
            list_requests_tool,
            ListRequestsParams,
            Dict[str, Any],
            (
                "List service request records from the ServiceNow sc_request table. "
                "Filter by state, requested_for, assigned_to, assignment_group, approval "
                "status, or free-text query. Supports pagination."
            ),
            "raw_dict",
        ),
        "get_request": (
            get_request_tool,
            GetRequestParams,
            Dict[str, Any],
            (
                "Retrieve a single service request from the sc_request table. "
                "Accepts a request number (e.g. REQ0010001) or a 32-character sys_id."
            ),
            "raw_dict",
        ),
        "create_request": (
            create_request_tool,
            CreateRequestParams,
            Dict[str, Any],
            (
                "Create a new service request in the ServiceNow sc_request table. "
                "Requires a short_description; optionally accepts requested_for, "
                "assignment_group, priority, urgency, impact, due_date, and comments."
            ),
            "raw_dict",
        ),
        "update_request": (
            update_request_tool,
            UpdateRequestParams,
            Dict[str, Any],
            (
                "Update an existing service request in the sc_request table by number or "
                "sys_id. Supply only the fields that need to change. Guards against "
                "empty-body calls."
            ),
            "raw_dict",
        ),
        "list_request_items": (
            list_request_items_tool,
            ListRequestItemsParams,
            Dict[str, Any],
            (
                "List the requested items (sc_req_item / RITM records) that belong to a "
                "service request. Accepts a request number (e.g. REQ0010001) or sys_id. "
                "Optionally filter by item state. Supports pagination."
            ),
            "raw_dict",
        ),
        # SLA Tools
        "list_sla_breach_definitions": (
            list_sla_breach_definitions_tool,
            ListSLABreachDefinitionsParams,
            Dict[str, Any],
            (
                "List active, breach-capable SLA definitions from the contract_sla table. "
                "Returns only SLAs that are active=true and have a duration set — i.e. "
                "those that can generate breach records in task_sla. "
                "Optional filters: type (SLA/OLA/UC), target table (e.g. 'incident'), "
                "and a name keyword search. Supports pagination."
            ),
            "raw_dict",
        ),
        "list_slas": (
            list_slas_tool,
            ListSLAsParams,
            Dict[str, Any],
            (
                "List SLA definitions from the ServiceNow contract_sla table. "
                "Filter by active status, type (SLA/OLA/UC), target table, or "
                "free-text query on name and description. Supports pagination."
            ),
            "raw_dict",
        ),
        "get_sla": (
            get_sla_tool,
            GetSLAParams,
            Dict[str, Any],
            (
                "Retrieve a single SLA definition by sys_id (32-char hex) or "
                "exact name from the contract_sla table."
            ),
            "raw_dict",
        ),
        "list_sla_breaches": (
            list_sla_breaches_tool,
            ListSLABreachesParams,
            Dict[str, Any],
            (
                "List SLA breach tracking records from the ServiceNow task_sla table. "
                "Each record shows the SLA state for one task/ticket. "
                "Filter by has_breached flag, stage (in_progress/breached/paused/completed), "
                "source table (e.g. 'incident'), a specific task sys_id, or a specific "
                "SLA definition sys_id. Supports pagination."
            ),
            "raw_dict",
        ),
        "get_sla_breach": (
            get_sla_breach_tool,
            GetSLABreachParams,
            Dict[str, Any],
            (
                "Retrieve a single SLA breach tracking record from the task_sla table "
                "by its sys_id. Returns breach status, stage, timing details (start_time, "
                "breach_time, end_time), percentage elapsed, and the associated task and "
                "SLA definition references."
            ),
            "raw_dict",
        ),
        "resolve_sla_breach": (
            resolve_sla_breach_tool,
            ResolveSLABreachParams,
            Dict[str, Any],
            (
                "Resolve an SLA breach tracking record by setting paused=true and "
                "stage=completed on the task_sla record. Use this to administratively "
                "close out a breach after the underlying task has been actioned. "
                "Accepts an optional work_notes field for audit purposes. "
                "Returns the updated sla_breach record."
            ),
            "raw_dict",
        ),
        # Problem Management Tools
        "list_problems": (
            list_problems_tool,
            ListProblemsParams,
            Dict[str, Any],
            (
                "List problem records from the ServiceNow problem table. "
                "Filter by state, assigned_to, assignment_group, category, known_error flag, "
                "or free-text query. Supports pagination."
            ),
            "raw_dict",
        ),
        "get_problem": (
            get_problem_tool,
            GetProblemParams,
            Dict[str, Any],
            (
                "Retrieve a single problem record by problem number (e.g. PRB0001234) "
                "or 32-character sys_id."
            ),
            "raw_dict",
        ),
        "create_problem": (
            create_problem_tool,
            CreateProblemParams,
            Dict[str, Any],
            (
                "Create a new problem record in the ServiceNow problem table. "
                "Requires a short_description. Optionally set category, priority, "
                "impact, urgency, assigned_to, assignment_group, workaround, and known_error."
            ),
            "raw_dict",
        ),
        "update_problem": (
            update_problem_tool,
            UpdateProblemParams,
            Dict[str, Any],
            (
                "Update an existing problem record by number or sys_id. Supply only the "
                "fields that need to change. Supports state, category, priority, cause_notes, "
                "fix_notes, work_notes, close_notes, and known_error flag."
            ),
            "raw_dict",
        ),
        "close_problem": (
            close_problem_tool,
            CloseProblemParams,
            Dict[str, Any],
            (
                "Close a problem record by setting its state to Closed (4). "
                "Accepts a problem number (e.g. PRB0001234) or sys_id. "
                "Optionally include close_notes, fix_notes, cause_notes, and work_notes."
            ),
            "raw_dict",
        ),
        # User Group Management Tools
        "list_user_groups": (
            list_user_groups_tool,
            ListUserGroupsParams,
            Dict[str, Any],
            (
                "List user groups from the ServiceNow sys_user_group table. "
                "Filter by name (LIKE), manager name or sys_id, active status, or "
                "free-text query across name and description. Supports pagination."
            ),
            "raw_dict",
        ),
        "get_user_group": (
            get_user_group_tool,
            GetUserGroupParams,
            Dict[str, Any],
            (
                "Retrieve a single user group by sys_id (32-char hex) or exact group name. "
                "Returns a 404-style error when the group cannot be found."
            ),
            "raw_dict",
        ),
        "add_user_to_group": (
            add_user_to_group_tool,
            AddUserToGroupParams,
            Dict[str, Any],
            (
                "Add a user to a ServiceNow group by creating a sys_user_grmember junction "
                "record. Accepts both group and user as either a sys_id or a name/username."
            ),
            "raw_dict",
        ),
        "remove_user_from_group": (
            remove_user_from_group_tool,
            RemoveUserFromGroupParams,
            Dict[str, Any],
            (
                "Remove a user from a ServiceNow group by deleting the sys_user_grmember "
                "junction record identified by its member_sys_id."
            ),
            "raw_dict",
        ),
        "list_group_members": (
            list_group_members_tool,
            ListGroupMembersParams,
            Dict[str, Any],
            (
                "List members of a ServiceNow user group from the sys_user_grmember table. "
                "Accepts a group sys_id or exact group name. Returns paginated member records "
                "with user display name and user sys_id."
            ),
            "raw_dict",
        ),
        # Notification Tools
        "list_notifications": (
            list_notifications_tool,
            ListNotificationsParams,
            Dict[str, Any],
            (
                "List outbound email notification records from the ServiceNow sysevent_email_log "
                "table. Filter by delivery state (sent/failed/skipped), notification type, "
                "recipient email address, source record sys_id, or creation date range. "
                "Supports pagination. Useful for auditing notification delivery and diagnosing "
                "failed emails."
            ),
            "raw_dict",
        ),
        # Role Management Tools
        "get_group_roles": (
            get_group_roles_tool,
            GetGroupRolesParams,
            Dict[str, Any],
            (
                "List roles assigned to a ServiceNow user group from the sys_group_has_role "
                "table. Accepts a group sys_id or exact group name. Returns paginated records "
                "with role name, role sys_id, and junction record sys_id (needed to remove a role)."
            ),
            "raw_dict",
        ),
        "assign_role_to_group": (
            assign_role_to_group_tool,
            AssignRoleToGroupParams,
            Dict[str, Any],
            (
                "Assign a role to a ServiceNow user group by creating a sys_group_has_role "
                "junction record. Accepts group and role as either a sys_id or a name "
                "(e.g. group_id='Help Desk', role_id='itil')."
            ),
            "raw_dict",
        ),
        "remove_role_from_group": (
            remove_role_from_group_tool,
            RemoveRoleFromGroupParams,
            Dict[str, Any],
            (
                "Remove a role from a ServiceNow user group by deleting the sys_group_has_role "
                "junction record identified by its member_sys_id. Use get_group_roles to obtain "
                "the junction record sys_id."
            ),
            "raw_dict",
        ),
        "list_user_roles": (
            list_user_roles_tool,
            ListUserRolesParams,
            Dict[str, Any],
            (
                "List roles assigned to a ServiceNow user from the sys_user_has_role table. "
                "Accepts a user sys_id or username. Optionally filter by include_inherited "
                "(True = only inherited roles, False = only direct grants). Returns paginated "
                "records with role name, inheritance flag, and granting role."
            ),
            "raw_dict",
        ),
    }
    return tool_definitions
