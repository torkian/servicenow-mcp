"""Tests for list_ci_dependencies in cmdb_relationship_tools.py."""

import unittest
from unittest.mock import MagicMock, patch

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.tools.cmdb_relationship_tools import (
    ListCIDependenciesParams,
    _build_edge,
    _extract_node,
    list_ci_dependencies,
)
from servicenow_mcp.utils.config import AuthConfig, AuthType, BasicAuthConfig, ServerConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CI_ROOT = "ci_root_001"

_EDGE_UP = {
    "sys_id": "edge_up_001",
    "parent": {"value": CI_ROOT, "display_value": "Root Server"},
    "child": {"value": "ci_dep_001", "display_value": "DB Server"},
    "type": {"value": "reltype_depends", "display_value": "Depends on::Used by"},
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-01-02 00:00:00",
    "_direction": "upstream",
}

_EDGE_DOWN = {
    "sys_id": "edge_dn_001",
    "parent": {"value": "ci_consumer_001", "display_value": "App Server"},
    "child": {"value": CI_ROOT, "display_value": "Root Server"},
    "type": {"value": "reltype_depends", "display_value": "Depends on::Used by"},
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_on": "2026-01-02 00:00:00",
    "_direction": "downstream",
}

_EDGE_STR = {
    "sys_id": "edge_str_001",
    "parent": CI_ROOT,
    "child": "ci_dep_str",
    "type": "reltype_str",
    "sys_created_on": "2026-02-01 00:00:00",
    "sys_updated_on": "2026-02-02 00:00:00",
    "_direction": "upstream",
}


def _make_config():
    auth_config = AuthConfig(
        type=AuthType.BASIC,
        basic=BasicAuthConfig(username="test", password="test"),
    )
    return ServerConfig(instance_url="https://dev99999.service-now.com", auth=auth_config)


def _make_auth():
    auth = MagicMock(spec=AuthManager)
    auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
    auth.instance_url = "https://dev99999.service-now.com"
    return auth


# ---------------------------------------------------------------------------
# _build_edge
# ---------------------------------------------------------------------------


class TestBuildEdge(unittest.TestCase):
    def test_upstream_dict_refs(self):
        edge = _build_edge(_EDGE_UP, "upstream")
        self.assertEqual(edge["sys_id"], "edge_up_001")
        self.assertEqual(edge["parent_sys_id"], CI_ROOT)
        self.assertEqual(edge["parent_name"], "Root Server")
        self.assertEqual(edge["child_sys_id"], "ci_dep_001")
        self.assertEqual(edge["child_name"], "DB Server")
        self.assertEqual(edge["type_sys_id"], "reltype_depends")
        self.assertEqual(edge["type_name"], "Depends on::Used by")
        self.assertEqual(edge["direction"], "upstream")

    def test_downstream_dict_refs(self):
        edge = _build_edge(_EDGE_DOWN, "downstream")
        self.assertEqual(edge["direction"], "downstream")
        self.assertEqual(edge["parent_sys_id"], "ci_consumer_001")
        self.assertEqual(edge["child_sys_id"], CI_ROOT)

    def test_string_refs(self):
        edge = _build_edge(_EDGE_STR, "upstream")
        self.assertEqual(edge["parent_sys_id"], CI_ROOT)
        self.assertEqual(edge["parent_name"], "")
        self.assertEqual(edge["child_sys_id"], "ci_dep_str")
        self.assertEqual(edge["type_sys_id"], "reltype_str")


# ---------------------------------------------------------------------------
# _extract_node
# ---------------------------------------------------------------------------


class TestExtractNode(unittest.TestCase):
    def test_upstream_returns_child(self):
        node = _extract_node(_EDGE_UP, CI_ROOT, "upstream")
        self.assertIsNotNone(node)
        self.assertEqual(node["sys_id"], "ci_dep_001")
        self.assertEqual(node["name"], "DB Server")
        self.assertEqual(node["direction"], "upstream")

    def test_downstream_returns_parent(self):
        node = _extract_node(_EDGE_DOWN, CI_ROOT, "downstream")
        self.assertIsNotNone(node)
        self.assertEqual(node["sys_id"], "ci_consumer_001")
        self.assertEqual(node["name"], "App Server")
        self.assertEqual(node["direction"], "downstream")

    def test_self_loop_returns_none(self):
        rec = {**_EDGE_UP, "child": {"value": CI_ROOT, "display_value": "Root Server"}}
        node = _extract_node(rec, CI_ROOT, "upstream")
        self.assertIsNone(node)

    def test_empty_neighbour_returns_none(self):
        rec = {**_EDGE_UP, "child": {"value": "", "display_value": ""}}
        node = _extract_node(rec, CI_ROOT, "upstream")
        self.assertIsNone(node)


# ---------------------------------------------------------------------------
# ListCIDependenciesParams validation
# ---------------------------------------------------------------------------


class TestListCIDependenciesParams(unittest.TestCase):
    def test_defaults(self):
        p = ListCIDependenciesParams(ci_sys_id="abc")
        self.assertEqual(p.direction, "both")
        self.assertEqual(p.depth, 1)
        self.assertEqual(p.limit, 50)
        self.assertIsNone(p.relationship_type)

    def test_depth_bounds(self):
        with self.assertRaises(Exception):
            ListCIDependenciesParams(ci_sys_id="abc", depth=0)
        with self.assertRaises(Exception):
            ListCIDependenciesParams(ci_sys_id="abc", depth=4)

    def test_direction_choices(self):
        for d in ("upstream", "downstream", "both"):
            p = ListCIDependenciesParams(ci_sys_id="abc", direction=d)
            self.assertEqual(p.direction, d)
        with self.assertRaises(Exception):
            ListCIDependenciesParams(ci_sys_id="abc", direction="invalid")


# ---------------------------------------------------------------------------
# list_ci_dependencies – happy paths
# ---------------------------------------------------------------------------


def _mock_response(records, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"result": records}
    resp.raise_for_status.return_value = None
    return resp


class TestListCIDependencies(unittest.TestCase):
    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_upstream_depth1(self, mock_req):
        mock_req.return_value = _mock_response([_EDGE_UP])
        result = list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT, "direction": "upstream", "depth": 1},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["ci_sys_id"], CI_ROOT)
        self.assertEqual(result["direction"], "upstream")
        self.assertEqual(len(result["edges"]), 1)
        self.assertEqual(result["edges"][0]["direction"], "upstream")
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["nodes"][0]["sys_id"], "ci_dep_001")
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_downstream_depth1(self, mock_req):
        mock_req.return_value = _mock_response([_EDGE_DOWN])
        result = list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT, "direction": "downstream", "depth": 1},
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["edges"]), 1)
        self.assertEqual(result["edges"][0]["direction"], "downstream")
        self.assertEqual(result["nodes"][0]["sys_id"], "ci_consumer_001")

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_both_directions_depth1(self, mock_req):
        mock_req.side_effect = [
            _mock_response([_EDGE_UP]),
            _mock_response([_EDGE_DOWN]),
        ]
        result = list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT, "direction": "both", "depth": 1},
        )
        self.assertTrue(result["success"])
        self.assertEqual(len(result["edges"]), 2)
        self.assertEqual(len(result["nodes"]), 2)
        self.assertEqual(result["count"], 2)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_depth2_bfs_second_level(self, mock_req):
        # depth=2, upstream: level-1 returns _EDGE_UP (finds ci_dep_001),
        # level-2 queries ci_dep_001 and finds one more hop.
        _edge_l2 = {
            "sys_id": "edge_l2_001",
            "parent": {"value": "ci_dep_001", "display_value": "DB Server"},
            "child": {"value": "ci_dep_002", "display_value": "Storage"},
            "type": {"value": "reltype_depends", "display_value": "Depends on::Used by"},
            "sys_created_on": "2026-01-01 00:00:00",
            "sys_updated_on": "2026-01-02 00:00:00",
            "_direction": "upstream",
        }
        mock_req.side_effect = [
            _mock_response([_EDGE_UP]),   # level 1 upstream
            _mock_response([_edge_l2]),   # level 2 upstream from ci_dep_001
        ]
        result = list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT, "direction": "upstream", "depth": 2},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["depth"], 2)
        self.assertEqual(len(result["edges"]), 2)
        self.assertEqual(len(result["nodes"]), 2)
        node_ids = {n["sys_id"] for n in result["nodes"]}
        self.assertIn("ci_dep_001", node_ids)
        self.assertIn("ci_dep_002", node_ids)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_empty_result(self, mock_req):
        mock_req.return_value = _mock_response([])
        result = list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["edges"], [])
        self.assertEqual(result["nodes"], [])
        self.assertEqual(result["count"], 0)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_relationship_type_filter_propagated(self, mock_req):
        mock_req.return_value = _mock_response([])
        list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT, "direction": "upstream", "relationship_type": "reltype_x"},
        )
        call_kwargs = mock_req.call_args
        query = call_kwargs[1]["params"]["sysparm_query"]
        self.assertIn("type=reltype_x", query)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_dedup_edges(self, mock_req):
        # Same edge returned twice (shouldn't happen, but must be deduped)
        mock_req.return_value = _mock_response([_EDGE_UP, _EDGE_UP])
        result = list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT, "direction": "upstream"},
        )
        self.assertEqual(result["count"], 1)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_dedup_nodes(self, mock_req):
        # Two edges pointing to same child CI — node should appear once
        _edge2 = {**_EDGE_UP, "sys_id": "edge_up_002"}
        mock_req.return_value = _mock_response([_EDGE_UP, _edge2])
        result = list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT, "direction": "upstream"},
        )
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["count"], 2)

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_no_frontier_stops_early(self, mock_req):
        # depth=3 but empty result at level 1 — should only call API once
        mock_req.return_value = _mock_response([])
        result = list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT, "direction": "upstream", "depth": 3},
        )
        self.assertTrue(result["success"])
        mock_req.assert_called_once()


# ---------------------------------------------------------------------------
# list_ci_dependencies – error paths
# ---------------------------------------------------------------------------


class TestListCIDependenciesErrors(unittest.TestCase):
    def test_missing_ci_sys_id(self):
        result = list_ci_dependencies(_make_auth(), _make_config(), {})
        self.assertFalse(result["success"])

    def test_no_instance_url(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = {"Authorization": "Bearer FAKE"}
        auth.instance_url = None
        cfg = MagicMock()
        cfg.instance_url = None
        result = list_ci_dependencies(auth, cfg, {"ci_sys_id": CI_ROOT})
        self.assertFalse(result["success"])

    def test_no_headers(self):
        auth = MagicMock(spec=AuthManager)
        auth.get_headers.return_value = None
        auth.instance_url = "https://dev99999.service-now.com"
        result = list_ci_dependencies(auth, _make_config(), {"ci_sys_id": CI_ROOT})
        self.assertFalse(result["success"])

    @patch("servicenow_mcp.tools.cmdb_relationship_tools._make_request")
    def test_network_error_skipped_gracefully(self, mock_req):
        import requests as _req

        mock_req.side_effect = _req.exceptions.ConnectionError("timeout")
        # Network error inside _fetch_rel_ci_edges is logged and swallowed;
        # result should still succeed with empty lists.
        result = list_ci_dependencies(
            _make_auth(),
            _make_config(),
            {"ci_sys_id": CI_ROOT, "direction": "upstream"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()
