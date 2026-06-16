# ServiceNow MCP Server

[![CI](https://github.com/torkian/servicenow-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/torkian/servicenow-mcp/actions/workflows/ci.yml)
[![CodeQL](https://github.com/torkian/servicenow-mcp/actions/workflows/codeql.yml/badge.svg)](https://github.com/torkian/servicenow-mcp/actions/workflows/codeql.yml)
[![codecov](https://codecov.io/gh/torkian/servicenow-mcp/graph/badge.svg)](https://codecov.io/gh/torkian/servicenow-mcp)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1665%20passed-brightgreen.svg)](https://github.com/torkian/servicenow-mcp/actions/workflows/ci.yml)

A Model Completion Protocol (MCP) server implementation for ServiceNow, allowing AI assistants to interact with ServiceNow instances.

> **This is a maintained fork of [echelon-ai-labs/servicenow-mcp](https://github.com/echelon-ai-labs/servicenow-mcp)** with active development, bug fixes, and new features.

## What's New (v3.1)

Adds the **change-approval workflow** — `list_change_approvals`, `get_change_approval`, `approve_change_approval`, and `reject_change_approval` — bringing the toolset to **180 tools**.

## What's New (v3.0)

The toolset has **nearly doubled — from 89 to 176 tools** — adding entire new domains plus a major quality pass.

### New Domains
- **CMDB** — full CI lifecycle, classes, CI lookup by name, relationships, and outage management
- **Asset Management** — assets and asset contracts (create / update / expire / list)
- **Problem Management** — create, track, update, close, and list problems
- **Service Requests** — request and request-item (RITM) management
- **SLA** — SLAs plus SLA-breach tracking and resolution
- **Bulk Operations** — mass updates across incidents, problems, and change requests
- **UI Policy** — create UI policies and UI policy actions
- **Attachments** — upload, list, fetch, and delete record attachments

### Also Added
- Incident tasks & comments, change tasks, and cancel/reopen for incidents and changes
- User-group membership, role assignment, and user-criteria tools; `get_user_by_email`
- Catalog lookup, variable sets and choices; `execute_script_include`; notifications & syslog

### Quality & Stability
- **1,604 tests passing** (0 failing) — orphaned tests removed, drifted tests fixed
- Shared helpers extracted (`utils/helpers.py`, `utils/tool_utils.py`) for pagination, rate limiting, retry, and date validation — removing ~740 lines of duplication
- Lint cleanup: Ruff config modernized, imports sorted, blind exception asserts narrowed

## What's New (v2.0)

### New Tools
- **Service Catalog Task (SCTASK) Management** — `get_sctask`, `list_sctasks`, `update_sctask` for managing service catalog tasks with state tracking, assignment, and time logging
- **Time Card Management** — `list_time_cards`, `create_time_card`, `update_time_card` for tracking hours worked per day against tasks
- **create_catalog_item** — Create new service catalog items (cherry-picked from upstream PR #60)

### Bug Fixes
- Fixed boolean logic bug in `update_sctask` where sys_id resolution always ran regardless of input format
- Fixed Dockerfile not copying `config/` directory, which broke tool package loading in Docker
- Fixed OAuth token response bodies being logged in plaintext (security fix, cherry-picked from upstream PR #59)
- Commented out 11 ghost tools in `tool_packages.yaml` that were listed but had no implementation

### Improvements
- Added missing `sse_server_example.py` referenced in README
- Added `.DS_Store` to `.gitignore` and removed tracked instances
- Updated README with accurate tool listings and usage examples
- Added `service_desk` and `agile_management` tool packages with SCTASK and time card support
- Corrected workflow tools documentation (was listing non-existent tools)

## Overview

This project implements an MCP server that enables AI assistants to connect to ServiceNow instances, retrieve data, and perform actions through the ServiceNow API. It serves as a bridge between AI tools and ServiceNow, allowing for seamless integration.

## Features

- Connect to ServiceNow instances using various authentication methods (Basic, OAuth, API Key)
- Query ServiceNow records and tables
- Create, update, and delete ServiceNow records
- Execute ServiceNow scripts and workflows
- Manage service catalog tasks (SCTASKs) and time cards
- Access and query the ServiceNow Service Catalog
- Analyze and optimize the ServiceNow Service Catalog
- Role-based tool packages for scoped access
- Debug mode for troubleshooting
- Support for both stdio and Server-Sent Events (SSE) communication

## Installation

### Prerequisites

- Python 3.11 or higher
- A ServiceNow instance with appropriate access credentials

### Setup

1. Clone this repository:
   ```
   git clone https://github.com/torkian/servicenow-mcp.git
   cd servicenow-mcp
   ```

2. Create a virtual environment and install the package:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```

3. Create a `.env` file with your ServiceNow credentials:
   ```
   SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
   SERVICENOW_USERNAME=your-username
   SERVICENOW_PASSWORD=your-password
   SERVICENOW_AUTH_TYPE=basic  # or oauth, api_key
   ```

## Usage

### Standard (stdio) Mode

To start the MCP server:

```
python -m servicenow_mcp.cli
```

Or with environment variables:

```
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com SERVICENOW_USERNAME=your-username SERVICENOW_PASSWORD=your-password SERVICENOW_AUTH_TYPE=basic python -m servicenow_mcp.cli
```

### Server-Sent Events (SSE) Mode

The ServiceNow MCP server can also run as a web server using Server-Sent Events (SSE) for communication, which allows for more flexible integration options.

#### Starting the SSE Server

You can start the SSE server using the provided CLI:

```
servicenow-mcp-sse --instance-url=https://your-instance.service-now.com --username=your-username --password=your-password
```

By default, the server will listen on `0.0.0.0:8080`. You can customize the host and port:

```
servicenow-mcp-sse --host=127.0.0.1 --port=8000
```

#### Connecting to the SSE Server

The SSE server exposes two main endpoints:

- `/sse` - The SSE connection endpoint
- `/messages/` - The endpoint for sending messages to the server

#### Example

See the `examples/sse_server_example.py` file for a complete example of setting up and running the SSE server.

```python
from servicenow_mcp.server import ServiceNowMCP
from servicenow_mcp.server_sse import create_starlette_app
from servicenow_mcp.utils.config import ServerConfig, AuthConfig, AuthType, BasicAuthConfig
import uvicorn

# Create server configuration
config = ServerConfig(
    instance_url="https://your-instance.service-now.com",
    auth=AuthConfig(
        type=AuthType.BASIC,
        config=BasicAuthConfig(
            username="your-username",
            password="your-password"
        )
    ),
    debug=True,
)

# Create ServiceNow MCP server
servicenow_mcp = ServiceNowMCP(config)

# Create Starlette app with SSE transport
app = create_starlette_app(servicenow_mcp, debug=True)

# Start the web server
uvicorn.run(app, host="0.0.0.0", port=8080)
```

## Tool Packaging (Optional)

To manage the number of tools exposed to the language model (especially in environments with limits), the ServiceNow MCP server supports loading subsets of tools called "packages". This is controlled via the `MCP_TOOL_PACKAGE` environment variable.

### Configuration

1.  **Environment Variable:** Set the `MCP_TOOL_PACKAGE` environment variable to the name of the desired package.
    ```bash
    export MCP_TOOL_PACKAGE=catalog_builder
    ```
2.  **Package Definitions:** The available packages and the tools they include are defined in `config/tool_packages.yaml`. You can customize this file to create your own packages.

### Behavior

-   If `MCP_TOOL_PACKAGE` is set to a valid package name defined in `config/tool_packages.yaml`, only the tools listed in that package will be loaded.
-   If `MCP_TOOL_PACKAGE` is **not set** or is empty, the `full` package (containing all tools) is loaded by default.
-   If `MCP_TOOL_PACKAGE` is set to an invalid package name, the `none` package is loaded (no tools except `list_tool_packages`), and a warning is logged.
-   Setting `MCP_TOOL_PACKAGE=none` explicitly loads no tools (except `list_tool_packages`).

### Available Packages (Default)

The default `config/tool_packages.yaml` includes the following role-based packages:

-   `service_desk`: Tools for incident handling, service catalog tasks (SCTASKs), time cards, and basic user/knowledge lookup.
-   `catalog_builder`: Tools for creating and managing service catalog items, categories, variables, and related scripting (UI Policies, User Criteria).
-   `change_coordinator`: Tools for managing the change request lifecycle, including tasks and approvals.
-   `knowledge_author`: Tools for creating and managing knowledge bases, categories, and articles.
-   `platform_developer`: Tools for server-side scripting (Script Includes), workflow development, and deployment (Changesets).
-   `system_administrator`: Tools for user/group management and viewing system logs.
-   `agile_management`: Tools for managing user stories, epics, scrum tasks, projects, service catalog tasks (SCTASKs), and time cards.
-   `full`: Includes all available tools (default).
-   `none`: Includes no tools (except `list_tool_packages`).

### Introspection Tool

-   **`list_tool_packages`**: Lists all available tool package names defined in the configuration and shows the currently loaded package. This tool is available in all packages except `none`.

## Available Tools

**Note:** Tool availability depends on the loaded tool package (see Tool Packaging above). By default (`full` package), all 180 tools are available.

### Incidents
- `add_comment`
- `create_incident`
- `delete_incident`
- `escalate_incident`
- `get_incident_by_number`
- `list_incidents`
- `reopen_incident`
- `resolve_incident`
- `update_incident`
- `close_incident_task`
- `create_incident_task`
- `list_incident_comments`
- `list_incident_tasks`

### Problems
- `close_problem`
- `create_problem`
- `get_problem`
- `list_problems`
- `update_problem`

### Changes
- `add_change_task`
- `approve_change`
- `approve_change_approval`
- `cancel_change_request`
- `create_change_request`
- `create_change_task`
- `get_change_approval`
- `get_change_request_details`
- `list_change_approvals`
- `list_change_requests`
- `list_change_tasks`
- `reject_change`
- `reject_change_approval`
- `reopen_change_request`
- `submit_change_for_approval`
- `update_change_request`

### Requests
- `create_request`
- `get_request`
- `list_request_items`
- `list_requests`
- `update_request`
- `get_sctask`
- `list_sctasks`
- `update_sctask`

### Service Catalog
- `create_catalog_category`
- `create_catalog_item`
- `get_catalog`
- `get_catalog_item`
- `list_catalog_categories`
- `list_catalog_items`
- `list_catalogs`
- `move_catalog_items`
- `update_catalog_category`
- `create_catalog_item_variable`
- `create_catalog_item_variable_set`
- `create_catalog_variable_choice`
- `delete_catalog_item_variable`
- `list_catalog_item_variables`
- `update_catalog_item_variable`
- `get_optimization_recommendations`
- `update_catalog_item`

### Knowledge
- `create_article`
- `create_category`
- `create_knowledge_article`
- `create_knowledge_base`
- `get_article`
- `list_articles`
- `list_articles_by_category`
- `list_categories`
- `list_knowledge_bases`
- `publish_article`
- `update_article`

### CMDB
- `create_ci`
- `create_ci_outage`
- `delete_ci_outage`
- `get_ci`
- `get_ci_by_name`
- `get_ci_outage`
- `list_cis`
- `list_cmdb_ci_outages`
- `list_cmdb_classes`
- `update_ci`
- `update_ci_outage`
- `create_ci_relationship`
- `delete_ci_relationship`
- `get_ci_relationship`
- `list_ci_relationship_types`
- `list_ci_relationships`

### Asset Management
- `create_asset`
- `delete_asset`
- `get_asset`
- `list_assets`
- `update_asset`
- `create_asset_contract`
- `expire_asset_contract`
- `get_asset_contract`
- `list_asset_contracts`
- `list_contract_assets`
- `update_asset_contract`

### SLA
- `get_sla`
- `get_sla_breach`
- `list_sla_breach_definitions`
- `list_sla_breaches`
- `list_slas`
- `resolve_sla_breach`

### Users, Groups & Roles
- `add_group_members`
- `create_group`
- `create_user`
- `get_user`
- `get_user_by_email`
- `list_groups`
- `list_users`
- `remove_group_members`
- `update_group`
- `update_user`
- `add_user_to_group`
- `get_user_group`
- `list_group_members`
- `list_user_groups`
- `remove_user_from_group`
- `assign_role_to_group`
- `get_group_roles`
- `list_user_roles`
- `remove_role_from_group`
- `create_user_criteria`
- `create_user_criteria_condition`
- `list_catalog_item_user_criteria`

### Workflows
- `activate_workflow`
- `add_workflow_activity`
- `create_workflow`
- `deactivate_workflow`
- `delete_workflow_activity`
- `get_workflow_activities`
- `get_workflow_details`
- `list_workflow_versions`
- `list_workflows`
- `reorder_workflow_activities`
- `update_workflow`
- `update_workflow_activity`

### Changesets & Script Includes
- `add_file_to_changeset`
- `commit_changeset`
- `create_changeset`
- `get_changeset_details`
- `list_changesets`
- `publish_changeset`
- `update_changeset`
- `create_script_include`
- `delete_script_include`
- `execute_script_include`
- `get_script_include`
- `list_script_includes`
- `update_script_include`

### Agile
- `create_story`
- `create_story_dependency`
- `delete_story_dependency`
- `list_stories`
- `list_story_dependencies`
- `update_story`
- `create_epic`
- `list_epics`
- `update_epic`
- `create_scrum_task`
- `list_scrum_tasks`
- `update_scrum_task`
- `create_project`
- `list_projects`
- `update_project`

### Bulk Operations
- `bulk_update_change_requests`
- `bulk_update_incidents`
- `bulk_update_problems`
- `execute_bulk_operations`

### Attachments
- `delete_attachment`
- `get_attachment`
- `list_attachments`

### UI Policy
- `create_ui_policy`
- `create_ui_policy_action`

### Notifications & Logs
- `list_notifications`
- `get_syslog_entry`
- `list_syslog_entries`

### Time Cards
- `create_time_card`
- `list_time_cards`
- `update_time_card`

### Using the MCP CLI

The ServiceNow MCP server can be installed with the MCP CLI, which provides a convenient way to register the server with Claude.

```bash
# Install the ServiceNow MCP server with environment variables from .env file
mcp install src/servicenow_mcp/server.py -f .env
```

This command will register the ServiceNow MCP server with Claude and configure it to use the environment variables from the .env file.

### Integration with Claude Desktop

To configure the ServiceNow MCP server in Claude Desktop:

1. Edit the Claude Desktop configuration file at `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the appropriate path for your OS:

```json
{
  "mcpServers": {
    "ServiceNow": {
      "command": "/Users/yourusername/dev/servicenow-mcp/.venv/bin/python",
      "args": [
        "-m",
        "servicenow_mcp.cli"
      ],
      "env": {
        "SERVICENOW_INSTANCE_URL": "https://your-instance.service-now.com",
        "SERVICENOW_USERNAME": "your-username",
        "SERVICENOW_PASSWORD": "your-password",
        "SERVICENOW_AUTH_TYPE": "basic"
      }
    }
  }
}
```

2. Restart Claude Desktop to apply the changes

### Example Usage with Claude

Below are some example natural language queries you can use with Claude to interact with ServiceNow via the MCP server:

#### Incident Management Examples
- "Create a new incident for a network outage in the east region"
- "Update the priority of incident INC0010001 to high"
- "Add a comment to incident INC0010001 saying the issue is being investigated"
- "Resolve incident INC0010001 with a note that the server was restarted"
- "List all high priority incidents assigned to the Network team"
- "List all active P1 incidents assigned to the Network team."

#### Service Catalog Examples
- "Show me all items in the service catalog"
- "List all service catalog categories"
- "Get details about the laptop request catalog item"
- "Show me all catalog items in the Hardware category"
- "Search for 'software' in the service catalog"
- "Create a new category called 'Cloud Services' in the service catalog"
- "Update the 'Hardware' category to rename it to 'IT Equipment'"
- "Move the 'Virtual Machine' catalog item to the 'Cloud Services' category"
- "Create a subcategory called 'Monitors' under the 'IT Equipment' category"
- "Reorganize our catalog by moving all software items to the 'Software' category"
- "Create a description field for the laptop request catalog item"
- "Add a dropdown field for selecting laptop models to catalog item"
- "List all form fields for the VPN access request catalog item"
- "Make the department field mandatory in the software request form"
- "Update the help text for the cost center field"
- "Show me all service catalogs in the system"
- "List all hardware catalog items."
- "Find the catalog item for 'New Laptop Request'."
- "Show me the variables for the 'New Laptop Request' item."
- "Create a new variable named 'department_code' for the 'New Hire Setup' catalog item. Make it a mandatory string field."

#### Catalog Optimization Examples
- "Analyze our service catalog and identify opportunities for improvement"
- "Find catalog items with poor descriptions that need improvement"
- "Identify catalog items with low usage that we might want to retire"
- "Find catalog items with high abandonment rates"
- "Optimize our Hardware category to improve user experience"

#### Change Management Examples
- "Create a change request for server maintenance to apply security patches tomorrow night"
- "Schedule a database upgrade for next Tuesday from 2 AM to 4 AM"
- "Add a task to the server maintenance change for pre-implementation checks"
- "Submit the server maintenance change for approval"
- "Approve the database upgrade change with comment: implementation plan looks thorough"
- "Show me all emergency changes scheduled for this week"
- "List all changes assigned to the Network team"
- "Create a normal change request to upgrade the production database server."
- "Update change CHG0012345, set the state to 'Implement'."

#### Agile Management Examples
- "Create a new user story for implementing a new reporting dashboard"
- "Update the 'Implement a new reporting dashboard' story to set it as blocked"
- "List all user stories assigned to the Data Analytics team"
- "Create a dependency between the 'Implement a new reporting dashboard' story and the 'Develop data extraction pipeline' story"
- "Delete the dependency between the 'Implement a new reporting dashboard' story and the 'Develop data extraction pipeline' story"
- "Create a new epic called 'Data Analytics Initiatives'"
- "Update the 'Data Analytics Initiatives' epic to set it as completed"
- "List all epics in the 'Data Analytics' project"
- "Create a new scrum task for the 'Implement a new reporting dashboard' story"
- "Update the 'Develop data extraction pipeline' scrum task to set it as completed"
- "List all scrum tasks in the 'Implement a new reporting dashboard' story"
- "Create a new project called 'Data Analytics Initiatives'"
- "Update the 'Data Analytics Initiatives' project to set it as completed"
- "List all projects in the 'Data Analytics' epic"

#### SCTASK Examples
- "Show me the details of SCTASK0525799"
- "List all open SCTASKs assigned to me"
- "List SCTASKs for the Desktop Support group"
- "Update SCTASK0525799 to mark it as work in progress and log 2 hours"
- "Close SCTASK0525799 with a note that the software was installed"

#### Time Card Examples
- "Show my time cards for this week"
- "List time cards for SCTASK0525799"
- "Create a time card for SCTASK0525799 with 8 hours on Monday and 4 hours on Tuesday"
- "Update my time card to add 4 hours on Wednesday"

#### Workflow Management Examples
- "Show me all active workflows in ServiceNow"
- "Get details about the incident approval workflow"
- "List all versions of the change request workflow"
- "Show me all activities in the service catalog request workflow"
- "Create a new workflow for handling software license requests"
- "Update the description of the incident escalation workflow"
- "Activate the new employee onboarding workflow"
- "Deactivate the old password reset workflow"
- "Add an approval activity to the software license request workflow"
- "Update the notification activity in the incident escalation workflow"
- "Delete the unnecessary activity from the change request workflow"
- "Reorder the activities in the service catalog request workflow"

#### Changeset Management Examples
- "List all changesets in ServiceNow"
- "Show me all changesets created by developer 'john.doe'"
- "Get details about changeset 'sys_update_set_123'"
- "Create a new changeset for the 'HR Portal' application"
- "Update the description of changeset 'sys_update_set_123'"
- "Commit changeset 'sys_update_set_123' with message 'Fixed login issue'"
- "Publish changeset 'sys_update_set_123' to production"
- "Add a file to changeset 'sys_update_set_123'"
- "Show me all changes in changeset 'sys_update_set_123'"

#### Knowledge Base Examples
- "Create a new knowledge base for the IT department"
- "List all knowledge bases in the organization"
- "Create a category called 'Network Troubleshooting' in the IT knowledge base"
- "Write an article about VPN setup in the Network Troubleshooting category"
- "Update the VPN setup article to include mobile device instructions"
- "Publish the VPN setup article so it's visible to all users"
- "List all articles in the Network Troubleshooting category"
- "Show me the details of the VPN setup article"
- "Find knowledge articles containing 'password reset' in the IT knowledge base"
- "Create a subcategory called 'Wireless Networks' under the Network Troubleshooting category"

#### User Management Examples
- "Create a new user Dr. Alice Radiology in the Radiology department"
- "Update Bob's user record to make him the manager of Alice"
- "Assign the ITIL role to Bob so he can approve change requests"
- "List all users in the Radiology department"
- "Create a new group called 'Biomedical Engineering' for managing medical devices"
- "Add an admin user to the Biomedical Engineering group as a member"
- "Update the Biomedical Engineering group to change its manager"
- "Remove a user from the Biomedical Engineering group"
- "Find all active users in the system with 'doctor' in their title"
- "Create a user that will act as an approver for the Radiology department"
- "List all IT support groups in the system"

#### UI Policy Examples
- "Create a UI policy for the 'Software Request' item (sys_id: abc...) named 'Show Justification' that applies when 'software_cost' is greater than 100."
- "For the UI policy 'Show Justification' (sys_id: def...), add an action to make the 'business_justification' variable visible and mandatory."
- "Create another action for policy 'Show Justification' to hide the 'alternative_software' variable."

### Example Scripts

The repository includes example scripts that demonstrate how to use the tools:

- **examples/catalog_optimization_example.py**: Demonstrates how to analyze and improve the ServiceNow Service Catalog
- **examples/change_management_demo.py**: Shows how to create and manage change requests in ServiceNow
- **examples/sse_server_example.py**: Demonstrates how to set up and run the SSE server

## Authentication Methods

### Basic Authentication

```
SERVICENOW_AUTH_TYPE=basic
SERVICENOW_USERNAME=your-username
SERVICENOW_PASSWORD=your-password
```

### OAuth Authentication

```
SERVICENOW_AUTH_TYPE=oauth
SERVICENOW_CLIENT_ID=your-client-id
SERVICENOW_CLIENT_SECRET=your-client-secret
SERVICENOW_TOKEN_URL=https://your-instance.service-now.com/oauth_token.do
```

### API Key Authentication

```
SERVICENOW_AUTH_TYPE=api_key
SERVICENOW_API_KEY=your-api-key
```

## Development

### Documentation

Additional documentation is available in the `docs` directory:

- [Catalog Integration](docs/catalog.md) - Detailed information about the Service Catalog integration
- [Catalog Optimization](docs/catalog_optimization_plan.md) - Detailed plan for catalog optimization features
- [Change Management](docs/change_management.md) - Detailed information about the Change Management tools
- [Workflow Management](docs/workflow_management.md) - Detailed information about the Workflow Management tools
- [Changeset Management](docs/changeset_management.md) - Detailed information about the Changeset Management tools

### Troubleshooting

#### Common Errors with Change Management Tools

1. **Error: `argument after ** must be a mapping, not CreateChangeRequestParams`**
   - This error occurs when you pass a `CreateChangeRequestParams` object instead of a dictionary to the `create_change_request` function.
   - Solution: Make sure you're passing a dictionary with the parameters, not a Pydantic model object.
   - Note: The change management tools have been updated to handle this error automatically. The functions will now attempt to unwrap parameters if they're incorrectly wrapped or passed as a Pydantic model object.

2. **Error: `Missing required parameter 'type'`**
   - This error occurs when you don't provide all required parameters for creating a change request.
   - Solution: Make sure to include all required parameters. For `create_change_request`, both `short_description` and `type` are required.

3. **Error: `Invalid value for parameter 'type'`**
   - This error occurs when you provide an invalid value for the `type` parameter.
   - Solution: Use one of the valid values: "normal", "standard", or "emergency".

4. **Error: `Cannot find get_headers method in either auth_manager or server_config`**
   - This error occurs when the parameters are passed in the wrong order or when using objects that don't have the required methods.
   - Solution: Make sure you're passing the `auth_manager` and `server_config` parameters in the correct order. The functions have been updated to handle parameter swapping automatically.

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Acknowledgments

This project is a maintained fork of [echelon-ai-labs/servicenow-mcp](https://github.com/echelon-ai-labs/servicenow-mcp), originally created by 100x Technology Inc under the MIT License.

### License

This project is licensed under the MIT License - see the LICENSE file for details.
