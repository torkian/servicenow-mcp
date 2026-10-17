"""Tests for KB article version history tools (list_kb_article_versions, get_kb_article_version)."""

from unittest.mock import MagicMock, patch

import requests

from servicenow_mcp.tools.knowledge_base import (
    GetKBArticleVersionParams,
    ListKBArticleVersionsParams,
    get_kb_article_version,
    list_kb_article_versions,
)


ARTICLE_SYS_ID = "abc123def456abc123def456abc123de"
VERSION_SYS_ID = "ver123def456abc123def456abc123de"


def _make_config(with_url=True):
    config = MagicMock()
    config.instance_url = "https://dev.service-now.com" if with_url else None
    config.api_url = "https://dev.service-now.com/api/now" if with_url else None
    config.timeout = 30
    return config


def _make_auth(with_headers=True):
    auth = MagicMock()
    auth.get_headers.return_value = {"Authorization": "Bearer token"} if with_headers else None
    return auth


def _version_row(idx=1):
    return {
        "sys_id": f"ver{idx:03d}000000000000000000000000000",
        "article": {"display_value": ARTICLE_SYS_ID, "value": ARTICLE_SYS_ID},
        "version": {"display_value": str(idx)},
        "short_description": {"display_value": f"Article v{idx}"},
        "workflow_state": {"display_value": "published"},
        "author": {"display_value": "John Doe"},
        "size": {"display_value": "1024"},
        "sys_created_on": f"2026-01-0{idx} 10:00:00",
        "sys_updated_on": f"2026-01-0{idx} 11:00:00",
        "sys_created_by": {"display_value": "admin"},
    }


# ---------------------------------------------------------------------------
# list_kb_article_versions
# ---------------------------------------------------------------------------

class TestListKBArticleVersions:

    def test_no_instance_url(self):
        result = list_kb_article_versions(
            _make_config(with_url=False),
            _make_auth(),
            ListKBArticleVersionsParams(article_id=ARTICLE_SYS_ID),
        )
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self):
        result = list_kb_article_versions(
            _make_config(),
            _make_auth(with_headers=False),
            ListKBArticleVersionsParams(article_id=ARTICLE_SYS_ID),
        )
        assert result["success"] is False
        assert "authentication" in result["message"]

    def test_success_returns_versions(self):
        rows = [_version_row(i) for i in range(1, 4)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": rows}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ):
            result = list_kb_article_versions(
                _make_config(),
                _make_auth(),
                ListKBArticleVersionsParams(article_id=ARTICLE_SYS_ID),
            )

        assert result["success"] is True
        assert len(result["versions"]) == 3
        assert result["versions"][0]["version"] == "1"
        assert result["versions"][0]["workflow_state"] == "published"
        assert result["versions"][0]["author"] == "John Doe"
        assert result["article_sys_id"] == ARTICLE_SYS_ID

    def test_empty_result(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ):
            result = list_kb_article_versions(
                _make_config(),
                _make_auth(),
                ListKBArticleVersionsParams(article_id=ARTICLE_SYS_ID),
            )

        assert result["success"] is True
        assert result["versions"] == []
        assert result["count"] == 0

    def test_workflow_state_filter(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ) as mock_req:
            list_kb_article_versions(
                _make_config(),
                _make_auth(),
                ListKBArticleVersionsParams(
                    article_id=ARTICLE_SYS_ID, workflow_state="published"
                ),
            )
            call_kwargs = mock_req.call_args
            query = call_kwargs[1]["params"]["sysparm_query"]
            assert "workflow_state=published" in query

    def test_pagination_params(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [_version_row(1)]}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ) as mock_req:
            list_kb_article_versions(
                _make_config(),
                _make_auth(),
                ListKBArticleVersionsParams(article_id=ARTICLE_SYS_ID, limit=5, offset=10),
            )
            params = mock_req.call_args[1]["params"]
            assert params["sysparm_limit"] == 5
            assert params["sysparm_offset"] == 10

    def test_unexpected_response_format(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = "not a dict"
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ):
            result = list_kb_article_versions(
                _make_config(),
                _make_auth(),
                ListKBArticleVersionsParams(article_id=ARTICLE_SYS_ID),
            )

        assert result["success"] is False
        assert "Unexpected" in result["message"]

    def test_request_exception(self):
        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=requests.RequestException("network error"),
        ):
            result = list_kb_article_versions(
                _make_config(),
                _make_auth(),
                ListKBArticleVersionsParams(article_id=ARTICLE_SYS_ID),
            )

        assert result["success"] is False
        assert "Failed to list KB article versions" in result["message"]

    def test_skips_non_dict_rows(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": [_version_row(1), "bad_row", _version_row(2)]}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ):
            result = list_kb_article_versions(
                _make_config(),
                _make_auth(),
                ListKBArticleVersionsParams(article_id=ARTICLE_SYS_ID),
            )

        assert result["success"] is True
        assert len(result["versions"]) == 2

    def test_has_more_pagination(self):
        rows = [_version_row(i) for i in range(1, 6)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": rows}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ):
            result = list_kb_article_versions(
                _make_config(),
                _make_auth(),
                ListKBArticleVersionsParams(article_id=ARTICLE_SYS_ID, limit=5, offset=0),
            )

        assert result["has_more"] is True
        assert result["next_offset"] == 5


# ---------------------------------------------------------------------------
# get_kb_article_version
# ---------------------------------------------------------------------------

class TestGetKBArticleVersion:

    def test_no_instance_url(self):
        result = get_kb_article_version(
            _make_config(with_url=False),
            _make_auth(),
            GetKBArticleVersionParams(version_id=VERSION_SYS_ID),
        )
        assert result["success"] is False
        assert "instance_url" in result["message"]

    def test_no_headers(self):
        result = get_kb_article_version(
            _make_config(),
            _make_auth(with_headers=False),
            GetKBArticleVersionParams(version_id=VERSION_SYS_ID),
        )
        assert result["success"] is False
        assert "authentication" in result["message"]

    def test_success(self):
        row = _version_row(3)
        row["sys_id"] = VERSION_SYS_ID
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": row}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ):
            result = get_kb_article_version(
                _make_config(),
                _make_auth(),
                GetKBArticleVersionParams(version_id=VERSION_SYS_ID),
            )

        assert result["success"] is True
        assert result["version"]["sys_id"] == VERSION_SYS_ID
        assert result["version"]["version"] == "3"
        assert result["version"]["workflow_state"] == "published"
        assert result["version"]["author"] == "John Doe"

    def test_404_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {}

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ):
            result = get_kb_article_version(
                _make_config(),
                _make_auth(),
                GetKBArticleVersionParams(version_id=VERSION_SYS_ID),
            )

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_empty_result(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {}}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ):
            result = get_kb_article_version(
                _make_config(),
                _make_auth(),
                GetKBArticleVersionParams(version_id=VERSION_SYS_ID),
            )

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_request_exception(self):
        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request",
            side_effect=requests.RequestException("timeout"),
        ):
            result = get_kb_article_version(
                _make_config(),
                _make_auth(),
                GetKBArticleVersionParams(version_id=VERSION_SYS_ID),
            )

        assert result["success"] is False
        assert "Failed to get KB article version" in result["message"]

    def test_string_display_values(self):
        row = {
            "sys_id": VERSION_SYS_ID,
            "article": ARTICLE_SYS_ID,
            "version": "2",
            "short_description": "Plain string description",
            "workflow_state": "draft",
            "author": "jane.doe",
            "size": "512",
            "sys_created_on": "2026-05-01 08:00:00",
            "sys_updated_on": "2026-05-01 09:00:00",
            "sys_created_by": "admin",
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": row}
        mock_resp.raise_for_status = MagicMock()

        with patch(
            "servicenow_mcp.tools.knowledge_base._make_request", return_value=mock_resp
        ):
            result = get_kb_article_version(
                _make_config(),
                _make_auth(),
                GetKBArticleVersionParams(version_id=VERSION_SYS_ID),
            )

        assert result["success"] is True
        assert result["version"]["version"] == "2"
        assert result["version"]["workflow_state"] == "draft"
        assert result["version"]["author"] == "jane.doe"
