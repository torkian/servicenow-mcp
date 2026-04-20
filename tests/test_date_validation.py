"""
Tests for date/datetime/duration field validators across tool models.
"""

import pytest
from pydantic import ValidationError

from servicenow_mcp.utils.helpers import (
    validate_duration_hhmmss,
    validate_servicenow_date,
    validate_servicenow_datetime,
)
from servicenow_mcp.tools.change_tools import (
    AddChangeTaskParams,
    CreateChangeRequestParams,
    UpdateChangeRequestParams,
)
from servicenow_mcp.tools.project_tools import CreateProjectParams, UpdateProjectParams
from servicenow_mcp.tools.sctask_tools import UpdateSCTaskParams
from servicenow_mcp.tools.syslog_tools import ListSyslogEntriesParams
from servicenow_mcp.tools.time_card_tools import CreateTimeCardParams, ListTimeCardsParams


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestValidateServicenowDatetime:
    def test_none_is_accepted(self):
        assert validate_servicenow_datetime(None) is None

    def test_date_only_format(self):
        assert validate_servicenow_datetime("2024-03-15") == "2024-03-15"

    def test_datetime_format(self):
        assert validate_servicenow_datetime("2024-03-15 09:30:00") == "2024-03-15 09:30:00"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            validate_servicenow_datetime("15/03/2024")

    def test_iso8601_with_T_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            validate_servicenow_datetime("2024-03-15T09:30:00")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            validate_servicenow_datetime("")

    def test_partial_date_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            validate_servicenow_datetime("2024-03")


class TestValidateServicenowDate:
    def test_none_is_accepted(self):
        assert validate_servicenow_date(None) is None

    def test_valid_date(self):
        assert validate_servicenow_date("2024-03-15") == "2024-03-15"

    def test_datetime_string_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            validate_servicenow_date("2024-03-15 09:30:00")

    def test_slashes_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            validate_servicenow_date("2024/03/15")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            validate_servicenow_date("")


class TestValidateDurationHhmmss:
    def test_none_is_accepted(self):
        assert validate_duration_hhmmss(None) is None

    def test_standard_duration(self):
        assert validate_duration_hhmmss("02:30:00") == "02:30:00"

    def test_large_hours(self):
        assert validate_duration_hhmmss("100:00:00") == "100:00:00"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid duration"):
            validate_duration_hhmmss("2:30")

    def test_missing_seconds_raises(self):
        with pytest.raises(ValueError, match="Invalid duration"):
            validate_duration_hhmmss("02:30")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid duration"):
            validate_duration_hhmmss("")


# ---------------------------------------------------------------------------
# Integration tests: Pydantic model validators
# ---------------------------------------------------------------------------


class TestCreateChangeRequestParamsValidation:
    def test_valid_datetime_accepted(self):
        p = CreateChangeRequestParams(
            short_description="Deploy patch",
            type="normal",
            start_date="2024-03-15 08:00:00",
            end_date="2024-03-15 10:00:00",
        )
        assert p.start_date == "2024-03-15 08:00:00"

    def test_valid_date_only_accepted(self):
        p = CreateChangeRequestParams(
            short_description="Deploy patch",
            type="normal",
            start_date="2024-03-15",
        )
        assert p.start_date == "2024-03-15"

    def test_none_dates_accepted(self):
        p = CreateChangeRequestParams(short_description="Deploy patch", type="normal")
        assert p.start_date is None
        assert p.end_date is None

    def test_invalid_start_date_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            CreateChangeRequestParams(
                short_description="Deploy patch",
                type="normal",
                start_date="03/15/2024",
            )
        assert "Invalid date" in str(exc_info.value)

    def test_invalid_end_date_raises(self):
        with pytest.raises(ValidationError):
            CreateChangeRequestParams(
                short_description="Deploy patch",
                type="normal",
                end_date="not-a-date",
            )


class TestUpdateChangeRequestParamsValidation:
    def test_valid_dates_accepted(self):
        p = UpdateChangeRequestParams(
            change_id="CHG001",
            start_date="2024-06-01 00:00:00",
            end_date="2024-06-02 00:00:00",
        )
        assert p.start_date == "2024-06-01 00:00:00"

    def test_invalid_date_raises(self):
        with pytest.raises(ValidationError):
            UpdateChangeRequestParams(change_id="CHG001", start_date="2024-6-1")


class TestAddChangeTaskParamsValidation:
    def test_valid_planned_dates(self):
        p = AddChangeTaskParams(
            change_id="CHG001",
            short_description="Task",
            planned_start_date="2024-03-15",
            planned_end_date="2024-03-16 17:00:00",
        )
        assert p.planned_start_date == "2024-03-15"

    def test_invalid_planned_date_raises(self):
        with pytest.raises(ValidationError):
            AddChangeTaskParams(
                change_id="CHG001",
                short_description="Task",
                planned_start_date="tomorrow",
            )


class TestCreateProjectParamsValidation:
    def test_valid_date_accepted(self):
        p = CreateProjectParams(
            short_description="Project Alpha",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        assert p.start_date == "2024-01-01"

    def test_invalid_date_raises(self):
        with pytest.raises(ValidationError):
            CreateProjectParams(short_description="Project Alpha", start_date="Jan 1 2024")


class TestUpdateProjectParamsValidation:
    def test_valid_dates_accepted(self):
        p = UpdateProjectParams(
            project_id="PRJ001",
            start_date="2024-01-01 00:00:00",
        )
        assert p.start_date == "2024-01-01 00:00:00"

    def test_invalid_date_raises(self):
        with pytest.raises(ValidationError):
            UpdateProjectParams(project_id="PRJ001", end_date="31-12-2024")


class TestListTimeCardsParamsValidation:
    def test_valid_week_start(self):
        p = ListTimeCardsParams(week_start="2024-03-11")
        assert p.week_start == "2024-03-11"

    def test_none_week_start_accepted(self):
        p = ListTimeCardsParams()
        assert p.week_start is None

    def test_invalid_week_start_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ListTimeCardsParams(week_start="2024-03-11 00:00:00")
        assert "Invalid date" in str(exc_info.value)

    def test_wrong_separator_raises(self):
        with pytest.raises(ValidationError):
            ListTimeCardsParams(week_start="2024/03/11")


class TestCreateTimeCardParamsValidation:
    def test_valid_week_start(self):
        p = CreateTimeCardParams(task_number="SCTASK001", week_start="2024-03-11")
        assert p.week_start == "2024-03-11"

    def test_invalid_week_start_raises(self):
        with pytest.raises(ValidationError):
            CreateTimeCardParams(task_number="SCTASK001", week_start="11-03-2024")


class TestListSyslogEntriesParamsValidation:
    def test_valid_datetime_accepted(self):
        p = ListSyslogEntriesParams(
            created_after="2024-03-01 00:00:00",
            created_before="2024-03-31 23:59:59",
        )
        assert p.created_after == "2024-03-01 00:00:00"

    def test_date_only_accepted(self):
        p = ListSyslogEntriesParams(created_after="2024-03-01")
        assert p.created_after == "2024-03-01"

    def test_none_accepted(self):
        p = ListSyslogEntriesParams()
        assert p.created_after is None
        assert p.created_before is None

    def test_invalid_created_after_raises(self):
        with pytest.raises(ValidationError):
            ListSyslogEntriesParams(created_after="2024.03.01")

    def test_invalid_created_before_raises(self):
        with pytest.raises(ValidationError):
            ListSyslogEntriesParams(created_before="March 1, 2024")


class TestUpdateSCTaskParamsValidation:
    def test_valid_duration_accepted(self):
        p = UpdateSCTaskParams(task_number="SCTASK001", time_worked="02:30:00")
        assert p.time_worked == "02:30:00"

    def test_none_accepted(self):
        p = UpdateSCTaskParams(task_number="SCTASK001")
        assert p.time_worked is None

    def test_invalid_duration_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            UpdateSCTaskParams(task_number="SCTASK001", time_worked="2h30m")
        assert "Invalid duration" in str(exc_info.value)

    def test_missing_seconds_raises(self):
        with pytest.raises(ValidationError):
            UpdateSCTaskParams(task_number="SCTASK001", time_worked="02:30")
