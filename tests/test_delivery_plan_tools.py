"""Tests for delivery_plan_tools.py (sc_cat_item_delivery_plan / sc_cat_item_delivery_task)."""

import pytest
from unittest.mock import MagicMock, patch

from servicenow_mcp.tools.delivery_plan_tools import (
    CreateDeliveryPlanParams,
    CreateDeliveryTaskParams,
    DeleteDeliveryPlanParams,
    GetDeliveryPlanParams,
    ListDeliveryPlansParams,
    ListDeliveryTasksParams,
    UpdateDeliveryPlanParams,
    _format_plan,
    _format_task,
    _resolve_cat_item_sys_id,
    _resolve_plan_sys_id,
    create_delivery_plan,
    create_delivery_task,
    delete_delivery_plan,
    get_delivery_plan,
    list_delivery_plans,
    list_delivery_tasks,
    update_delivery_plan,
)

INSTANCE_URL = "https://instance.service-now.com"
PLAN_SYS_ID = "a" * 32
TASK_SYS_ID = "b" * 32
ITEM_SYS_ID = "c" * 32


@pytest.fixture
def auth_manager():
    am = MagicMock()
    am.get_headers.return_value = {"Authorization": "Bearer token"}
    return am


@pytest.fixture
def config():
    cfg = MagicMock()
    cfg.instance_url = INSTANCE_URL
    return cfg


RAW_PLAN = {
    "sys_id": PLAN_SYS_ID,
    "name": "Standard Approval",
    "description": "Standard two-step approval",
    "active": "true",
    "cat_item": {"display_value": "Laptop Request", "value": ITEM_SYS_ID},
    "workflow": {"display_value": "Approval WF", "value": "d" * 32},
    "sys_created_on": "2026-01-01 10:00:00",
    "sys_updated_on": "2026-06-01 09:00:00",
    "sys_created_by": "admin",
}

RAW_TASK = {
    "sys_id": TASK_SYS_ID,
    "name": "Manager Approval",
    "description": "Requires manager sign-off",
    "active": "true",
    "order": "100",
    "delivery_plan": {"display_value": "Standard Approval", "value": PLAN_SYS_ID},
    "approval_group": {"display_value": "IT Managers", "value": "e" * 32},
    "assigned_to": {"display_value": "John Doe", "value": "f" * 32},
    "mandatory": "true",
    "sys_created_on": "2026-01-02 10:00:00",
    "sys_updated_on": "2026-06-02 08:00:00",
}


# ---------------------------------------------------------------------------
# _format_plan / _format_task
# ---------------------------------------------------------------------------


def test_format_plan_basic():
    result = _format_plan(RAW_PLAN)
    assert result["sys_id"] == PLAN_SYS_ID
    assert result["name"] == "Standard Approval"
    assert result["cat_item"] == "Laptop Request"
    assert result["workflow"] == "Approval WF"
    assert result["active"] == "true"


def test_format_plan_plain_strings():
    raw = dict(RAW_PLAN)
    raw["cat_item"] = ITEM_SYS_ID
    raw["workflow"] = None
    result = _format_plan(raw)
    assert result["cat_item"] == ITEM_SYS_ID
    assert result["workflow"] is None


def test_format_task_basic():
    result = _format_task(RAW_TASK)
    assert result["sys_id"] == TASK_SYS_ID
    assert result["name"] == "Manager Approval"
    assert result["delivery_plan"] == "Standard Approval"
    assert result["approval_group"] == "IT Managers"
    assert result["assigned_to"] == "John Doe"
    assert result["mandatory"] == "true"


def test_format_task_plain_strings():
    raw = dict(RAW_TASK)
    raw["approval_group"] = "e" * 32
    raw["assigned_to"] = None
    result = _format_task(raw)
    assert result["approval_group"] == "e" * 32
    assert result["assigned_to"] is None


# ---------------------------------------------------------------------------
# _resolve_plan_sys_id
# ---------------------------------------------------------------------------


def test_resolve_plan_sys_id_hex():
    result = _resolve_plan_sys_id(INSTANCE_URL, {}, PLAN_SYS_ID)
    assert result == PLAN_SYS_ID


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_resolve_plan_sys_id_by_name(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
    )
    mock_get.return_value.raise_for_status = MagicMock()
    result = _resolve_plan_sys_id(INSTANCE_URL, {}, "Standard Approval")
    assert result == PLAN_SYS_ID


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_resolve_plan_sys_id_not_found(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
    )
    mock_get.return_value.raise_for_status = MagicMock()
    result = _resolve_plan_sys_id(INSTANCE_URL, {}, "Unknown Plan")
    assert result is None


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_resolve_plan_sys_id_exception(mock_get):
    mock_get.side_effect = Exception("network error")
    result = _resolve_plan_sys_id(INSTANCE_URL, {}, "Bad Plan")
    assert result is None


# ---------------------------------------------------------------------------
# _resolve_cat_item_sys_id
# ---------------------------------------------------------------------------


def test_resolve_cat_item_sys_id_hex():
    assert _resolve_cat_item_sys_id(INSTANCE_URL, {}, ITEM_SYS_ID) == ITEM_SYS_ID


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_resolve_cat_item_sys_id_by_name(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": ITEM_SYS_ID}]},
    )
    mock_get.return_value.raise_for_status = MagicMock()
    result = _resolve_cat_item_sys_id(INSTANCE_URL, {}, "Laptop Request")
    assert result == ITEM_SYS_ID


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_resolve_cat_item_sys_id_not_found(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
    )
    mock_get.return_value.raise_for_status = MagicMock()
    assert _resolve_cat_item_sys_id(INSTANCE_URL, {}, "Missing Item") is None


# ---------------------------------------------------------------------------
# list_delivery_plans
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_plans_success(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [RAW_PLAN]},
    )
    mock_get.return_value.raise_for_status = MagicMock()
    result = list_delivery_plans(config, auth_manager, ListDeliveryPlansParams())
    assert "records" in result
    assert result["count"] == 1
    assert result["records"][0]["name"] == "Standard Approval"


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_plans_with_filters(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
    )
    mock_get.return_value.raise_for_status = MagicMock()
    result = list_delivery_plans(
        config,
        auth_manager,
        ListDeliveryPlansParams(name="Standard", active=True, query="sys_created_by=admin"),
    )
    assert result["count"] == 0
    call_params = mock_get.call_args[1]["params"]
    assert "nameLIKEStandard" in call_params["sysparm_query"]
    assert "active=true" in call_params["sysparm_query"]
    assert "sys_created_by=admin" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_plans_with_cat_item_filter(mock_get, config, auth_manager):
    # First call: item resolver → found; second call: list query
    mock_get.side_effect = [
        MagicMock(
            status_code=200,
            json=lambda: {"result": [{"sys_id": ITEM_SYS_ID}]},
            raise_for_status=MagicMock(),
        ),
        MagicMock(
            status_code=200,
            json=lambda: {"result": [RAW_PLAN]},
            raise_for_status=MagicMock(),
        ),
    ]
    result = list_delivery_plans(
        config,
        auth_manager,
        ListDeliveryPlansParams(cat_item_id="Laptop Request"),
    )
    assert result["count"] == 1


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_plans_has_more(mock_get, config, auth_manager):
    plans = [RAW_PLAN] * 5
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": plans},
    )
    mock_get.return_value.raise_for_status = MagicMock()
    result = list_delivery_plans(config, auth_manager, ListDeliveryPlansParams(limit=5))
    assert result["has_more"] is True
    assert result["next_offset"] == 5


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_plans_http_error(mock_get, config, auth_manager):
    resp = MagicMock(status_code=500)
    mock_get.return_value = resp
    resp.raise_for_status.side_effect = Exception("500 Server Error")
    # Patch to return HTTPError
    import requests as req_mod
    http_err = req_mod.HTTPError(response=MagicMock(status_code=500))
    resp.raise_for_status.side_effect = http_err
    result = list_delivery_plans(config, auth_manager, ListDeliveryPlansParams())
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_plans_request_exception(mock_get, config, auth_manager):
    import requests as req_mod
    mock_get.side_effect = req_mod.RequestException("timeout")
    result = list_delivery_plans(config, auth_manager, ListDeliveryPlansParams())
    assert "error" in result


# ---------------------------------------------------------------------------
# get_delivery_plan
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_get_delivery_plan_success(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": RAW_PLAN},
    )
    mock_get.return_value.raise_for_status = MagicMock()
    result = get_delivery_plan(config, auth_manager, GetDeliveryPlanParams(plan_id=PLAN_SYS_ID))
    assert "plan" in result
    assert result["plan"]["sys_id"] == PLAN_SYS_ID


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_get_delivery_plan_not_found_resolver(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
    )
    mock_get.return_value.raise_for_status = MagicMock()
    result = get_delivery_plan(config, auth_manager, GetDeliveryPlanParams(plan_id="Unknown"))
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_get_delivery_plan_404(mock_get, config, auth_manager):
    # Resolver returns sys_id, then GET returns 404
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return MagicMock(
                status_code=200,
                json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
                raise_for_status=MagicMock(),
            )
        m = MagicMock(status_code=404)
        m.raise_for_status = MagicMock()
        return m

    mock_get.side_effect = side_effect
    result = get_delivery_plan(config, auth_manager, GetDeliveryPlanParams(plan_id="Some Plan"))
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_get_delivery_plan_empty_result(mock_get, config, auth_manager):
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        m = MagicMock(status_code=200, raise_for_status=MagicMock())
        if call_count["n"] == 1:
            m.json = lambda: {"result": [{"sys_id": PLAN_SYS_ID}]}
        else:
            m.json = lambda: {"result": None}
        return m

    mock_get.side_effect = side_effect
    result = get_delivery_plan(config, auth_manager, GetDeliveryPlanParams(plan_id="Some Plan"))
    assert "error" in result


# ---------------------------------------------------------------------------
# create_delivery_plan
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.post")
def test_create_delivery_plan_success(mock_post, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": ITEM_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    mock_post.return_value = MagicMock(
        status_code=201,
        json=lambda: {"result": RAW_PLAN},
        raise_for_status=MagicMock(),
    )
    result = create_delivery_plan(
        config,
        auth_manager,
        CreateDeliveryPlanParams(name="Standard Approval", cat_item_id="Laptop Request"),
    )
    assert result["success"] is True
    assert "plan" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_create_delivery_plan_item_not_found(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
        raise_for_status=MagicMock(),
    )
    result = create_delivery_plan(
        config,
        auth_manager,
        CreateDeliveryPlanParams(name="Plan", cat_item_id="Nonexistent Item"),
    )
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.post")
def test_create_delivery_plan_http_error(mock_post, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": ITEM_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    import requests as req_mod
    mock_post.return_value = MagicMock(status_code=400)
    mock_post.return_value.raise_for_status.side_effect = req_mod.HTTPError(
        response=MagicMock(status_code=400)
    )
    result = create_delivery_plan(
        config,
        auth_manager,
        CreateDeliveryPlanParams(
            name="Plan", cat_item_id=ITEM_SYS_ID, description="desc", workflow="w" * 32
        ),
    )
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.post")
def test_create_delivery_plan_request_exception(mock_post, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": ITEM_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    import requests as req_mod
    mock_post.side_effect = req_mod.RequestException("connection refused")
    result = create_delivery_plan(
        config,
        auth_manager,
        CreateDeliveryPlanParams(name="Plan", cat_item_id=ITEM_SYS_ID),
    )
    assert "error" in result


# ---------------------------------------------------------------------------
# update_delivery_plan
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.patch")
def test_update_delivery_plan_success(mock_patch, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    mock_patch.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": RAW_PLAN},
        raise_for_status=MagicMock(),
    )
    result = update_delivery_plan(
        config,
        auth_manager,
        UpdateDeliveryPlanParams(plan_id="Standard Approval", name="New Name", active=False),
    )
    assert result["success"] is True


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_update_delivery_plan_not_found(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
        raise_for_status=MagicMock(),
    )
    result = update_delivery_plan(
        config,
        auth_manager,
        UpdateDeliveryPlanParams(plan_id="Missing Plan", name="X"),
    )
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_update_delivery_plan_no_fields(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    result = update_delivery_plan(
        config,
        auth_manager,
        UpdateDeliveryPlanParams(plan_id=PLAN_SYS_ID),
    )
    assert "error" in result
    assert "No fields" in result["error"]


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.patch")
def test_update_delivery_plan_404_on_patch(mock_patch, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    mock_patch.return_value = MagicMock(status_code=404, raise_for_status=MagicMock())
    result = update_delivery_plan(
        config,
        auth_manager,
        UpdateDeliveryPlanParams(plan_id=PLAN_SYS_ID, description="new desc"),
    )
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.patch")
def test_update_delivery_plan_request_exception(mock_patch, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    import requests as req_mod
    mock_patch.side_effect = req_mod.RequestException("timeout")
    result = update_delivery_plan(
        config,
        auth_manager,
        UpdateDeliveryPlanParams(plan_id=PLAN_SYS_ID, workflow="w" * 32),
    )
    assert "error" in result


# ---------------------------------------------------------------------------
# delete_delivery_plan
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.delete")
def test_delete_delivery_plan_success_204(mock_delete, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    mock_delete.return_value = MagicMock(status_code=204, raise_for_status=MagicMock())
    result = delete_delivery_plan(
        config, auth_manager, DeleteDeliveryPlanParams(plan_id=PLAN_SYS_ID)
    )
    assert result["success"] is True


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.delete")
def test_delete_delivery_plan_success_200(mock_delete, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    mock_delete.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
    result = delete_delivery_plan(
        config, auth_manager, DeleteDeliveryPlanParams(plan_id=PLAN_SYS_ID)
    )
    assert result["success"] is True


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_delete_delivery_plan_resolver_not_found(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
        raise_for_status=MagicMock(),
    )
    result = delete_delivery_plan(
        config, auth_manager, DeleteDeliveryPlanParams(plan_id="Missing Plan")
    )
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.delete")
def test_delete_delivery_plan_404_on_delete(mock_delete, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    mock_delete.return_value = MagicMock(status_code=404, raise_for_status=MagicMock())
    result = delete_delivery_plan(
        config, auth_manager, DeleteDeliveryPlanParams(plan_id=PLAN_SYS_ID)
    )
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.delete")
def test_delete_delivery_plan_request_exception(mock_delete, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    import requests as req_mod
    mock_delete.side_effect = req_mod.RequestException("network error")
    result = delete_delivery_plan(
        config, auth_manager, DeleteDeliveryPlanParams(plan_id=PLAN_SYS_ID)
    )
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
@patch("servicenow_mcp.tools.delivery_plan_tools.requests.delete")
def test_delete_delivery_plan_http_error(mock_delete, mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [{"sys_id": PLAN_SYS_ID}]},
        raise_for_status=MagicMock(),
    )
    import requests as req_mod
    mock_delete.return_value = MagicMock(status_code=403)
    mock_delete.return_value.raise_for_status.side_effect = req_mod.HTTPError(
        response=MagicMock(status_code=403)
    )
    result = delete_delivery_plan(
        config, auth_manager, DeleteDeliveryPlanParams(plan_id=PLAN_SYS_ID)
    )
    assert "error" in result


# ---------------------------------------------------------------------------
# list_delivery_tasks
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_tasks_success(mock_get, config, auth_manager):
    # PLAN_SYS_ID is a hex sys_id so no resolver HTTP call is made
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": [RAW_TASK]},
        raise_for_status=MagicMock(),
    )
    result = list_delivery_tasks(
        config, auth_manager, ListDeliveryTasksParams(plan_id=PLAN_SYS_ID)
    )
    assert result["count"] == 1
    assert result["records"][0]["name"] == "Manager Approval"


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_tasks_plan_not_found(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
        raise_for_status=MagicMock(),
    )
    result = list_delivery_tasks(
        config, auth_manager, ListDeliveryTasksParams(plan_id="Unknown Plan")
    )
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_tasks_active_filter(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
        raise_for_status=MagicMock(),
    )
    result = list_delivery_tasks(
        config, auth_manager, ListDeliveryTasksParams(plan_id=PLAN_SYS_ID, active=False)
    )
    assert result["count"] == 0
    call_params = mock_get.call_args[1]["params"]
    assert "active=false" in call_params["sysparm_query"]


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_tasks_has_more(mock_get, config, auth_manager):
    tasks = [RAW_TASK] * 5
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": tasks},
        raise_for_status=MagicMock(),
    )
    result = list_delivery_tasks(
        config, auth_manager, ListDeliveryTasksParams(plan_id=PLAN_SYS_ID, limit=5)
    )
    assert result["has_more"] is True
    assert result["next_offset"] == 5


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_list_delivery_tasks_request_exception(mock_get, config, auth_manager):
    import requests as req_mod
    mock_get.side_effect = req_mod.RequestException("timeout")
    result = list_delivery_tasks(
        config, auth_manager, ListDeliveryTasksParams(plan_id=PLAN_SYS_ID)
    )
    assert "error" in result


# ---------------------------------------------------------------------------
# create_delivery_task
# ---------------------------------------------------------------------------


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.post")
def test_create_delivery_task_success(mock_post, config, auth_manager):
    # PLAN_SYS_ID is hex so no resolver HTTP call
    mock_post.return_value = MagicMock(
        status_code=201,
        json=lambda: {"result": RAW_TASK},
        raise_for_status=MagicMock(),
    )
    result = create_delivery_task(
        config,
        auth_manager,
        CreateDeliveryTaskParams(plan_id=PLAN_SYS_ID, name="Manager Approval"),
    )
    assert result["success"] is True
    assert "task" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.post")
def test_create_delivery_task_with_all_fields(mock_post, config, auth_manager):
    mock_post.return_value = MagicMock(
        status_code=201,
        json=lambda: {"result": RAW_TASK},
        raise_for_status=MagicMock(),
    )
    result = create_delivery_task(
        config,
        auth_manager,
        CreateDeliveryTaskParams(
            plan_id=PLAN_SYS_ID,
            name="Manager Approval",
            description="Approve",
            order=100,
            approval_group="e" * 32,
            assigned_to="f" * 32,
            mandatory=False,
            active=False,
        ),
    )
    assert result["success"] is True
    body = mock_post.call_args[1]["json"]
    assert body["order"] == "100"
    assert body["mandatory"] == "false"
    assert body["active"] == "false"


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.get")
def test_create_delivery_task_plan_not_found(mock_get, config, auth_manager):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"result": []},
        raise_for_status=MagicMock(),
    )
    result = create_delivery_task(
        config,
        auth_manager,
        CreateDeliveryTaskParams(plan_id="Missing Plan", name="Task"),
    )
    assert "error" in result


@patch("servicenow_mcp.tools.delivery_plan_tools.requests.post")
def test_create_delivery_task_request_exception(mock_post, config, auth_manager):
    import requests as req_mod
    mock_post.side_effect = req_mod.RequestException("timeout")
    result = create_delivery_task(
        config,
        auth_manager,
        CreateDeliveryTaskParams(plan_id=PLAN_SYS_ID, name="Task"),
    )
    assert "error" in result
