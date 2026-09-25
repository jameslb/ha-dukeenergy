"""Tests for retry classification, diagnostics, and poll scheduling."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from aiodukeenergy import DukeEnergyAuthError, DukeEnergyBlockedError
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.duke_energy.coordinator import DukeEnergyCoordinator
from custom_components.duke_energy.sensor import (
    DukeEnergyLastChangedSensor,
    DukeEnergyLastUpdatedSensor,
    DukeEnergyNextUpdateSensor,
    DukeEnergyStatusSensor,
)

EARLIEST_UPDATE_HOUR = 7
LATEST_UPDATE_HOUR = 21


@pytest.mark.asyncio
async def test_blocked_request_is_retryable_not_reauth() -> None:
    """An edge rejection must not invalidate otherwise valid credentials."""
    coordinator = DukeEnergyCoordinator.__new__(DukeEnergyCoordinator)
    coordinator.api = SimpleNamespace(
        get_meters=AsyncMock(side_effect=DukeEnergyBlockedError("blocked"))
    )

    with pytest.raises(UpdateFailed, match="will retry"):
        await coordinator._async_update_data_locked()


@pytest.mark.asyncio
async def test_real_auth_failure_requests_reauth() -> None:
    """A genuine authentication failure still initiates reauthentication."""
    coordinator = DukeEnergyCoordinator.__new__(DukeEnergyCoordinator)
    coordinator.api = SimpleNamespace(
        get_meters=AsyncMock(side_effect=DukeEnergyAuthError("invalid token"))
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data_locked()


@pytest.mark.asyncio
async def test_poll_schedule_is_stable_distributed_and_daytime() -> None:
    """The same entry/day gets a stable future poll in a daytime window."""
    timezone = ZoneInfo("America/New_York")
    now = datetime(2026, 9, 25, 8, 0, tzinfo=timezone)
    coordinator = DukeEnergyCoordinator.__new__(DukeEnergyCoordinator)
    coordinator.config_entry = SimpleNamespace(entry_id="test-entry")
    coordinator._async_get_service_timezone = AsyncMock(return_value=timezone)

    with patch(
        "custom_components.duke_energy.coordinator.dt_util.now", return_value=now
    ):
        await coordinator._schedule_next_update()
        first = coordinator.next_update
        first_interval = coordinator.update_interval
        await coordinator._schedule_next_update()

    assert first == coordinator.next_update
    assert first_interval == coordinator.update_interval
    assert now + timedelta(minutes=1) < first
    assert EARLIEST_UPDATE_HOUR <= first.hour <= LATEST_UPDATE_HOUR


@pytest.mark.asyncio
async def test_failed_refresh_updates_diagnostic_status() -> None:
    """Failed refreshes remain observable through the status diagnostic."""
    coordinator = DukeEnergyCoordinator.__new__(DukeEnergyCoordinator)
    coordinator.status = "idle"
    coordinator._schedule_next_update = AsyncMock()
    coordinator._async_update_data_locked = AsyncMock(
        side_effect=UpdateFailed("temporary")
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.status == "failed"


def test_diagnostic_entities_are_disabled_by_default() -> None:
    """Diagnostics are available without cluttering existing installations."""
    diagnostic_classes = (
        DukeEnergyLastUpdatedSensor,
        DukeEnergyLastChangedSensor,
        DukeEnergyNextUpdateSensor,
        DukeEnergyStatusSensor,
    )
    assert all(
        entity._attr_entity_registry_enabled_default is False
        for entity in diagnostic_classes
    )
    assert DukeEnergyLastUpdatedSensor._attr_device_class is SensorDeviceClass.TIMESTAMP
    assert DukeEnergyNextUpdateSensor._attr_device_class is SensorDeviceClass.TIMESTAMP
    assert DukeEnergyStatusSensor._attr_device_class is SensorDeviceClass.ENUM
