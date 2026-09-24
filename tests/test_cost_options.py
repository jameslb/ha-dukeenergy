"""Tests for local Duke Energy cost-option updates."""

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from types import MethodType
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.duke_energy.const import (
    CONF_COST_TRACKING,
    CONF_EFFECTIVE_DATE,
    CONF_ENABLED,
    CONF_RATE,
    CONF_RATES,
)
from custom_components.duke_energy.coordinator import DukeEnergyCoordinator
from custom_components.duke_energy.cost import CostLedger, ManualRateProvider

pytestmark = pytest.mark.asyncio

METER = {
    "serviceType": "ELECTRIC",
    "serialNum": "serial",
    "agreementActiveDate": "2026-01-01T00:00:00",
}
INTERVAL = datetime(2026, 6, 1, tzinfo=UTC)


def _options(
    rate: str | None,
    effective_date: str = "2026-01-01",
    *,
    enabled: bool = True,
) -> dict[str, object]:
    """Build manual electric rate options."""
    return {
        CONF_COST_TRACKING: {
            "ELECTRIC": {
                CONF_ENABLED: enabled,
                CONF_RATES: [
                    {
                        CONF_EFFECTIVE_DATE: effective_date,
                        CONF_RATE: rate,
                    }
                ],
            }
        }
    }


def _ledger() -> CostLedger:
    """Build an in-memory ledger without a Home Assistant Store."""
    ledger = object.__new__(CostLedger)
    ledger._data = {"meters": {}}
    ledger._dirty = False
    ledger._store = MagicMock()
    ledger._store.async_save = AsyncMock()
    return ledger


def _coordinator(
    old_options: dict[str, object],
    *,
    covered_from: date = date(2026, 1, 1),
) -> DukeEnergyCoordinator:
    """Build the coordinator surface needed by local option updates."""
    coordinator = object.__new__(DukeEnergyCoordinator)
    coordinator._cost_update_lock = asyncio.Lock()
    coordinator.rate_provider = ManualRateProvider(old_options)
    coordinator.cost_ledger = _ledger()
    coordinator.cost_ledger.update(
        "electric_serial",
        "ELECTRIC",
        {INTERVAL: {"energy": 10}},
        coordinator.rate_provider,
    )
    coordinator.cost_ledger.mark_history_covered_from("electric_serial", covered_from)
    coordinator.meters = {"serial": METER}
    coordinator.api = MagicMock()
    coordinator.api.get_energy_usage = AsyncMock()
    coordinator._async_get_historical_usage = AsyncMock(return_value={})
    coordinator._async_import_dirty_cost_statistics = AsyncMock()
    coordinator.async_set_updated_data = MagicMock()
    return coordinator


@pytest.mark.parametrize(
    ("old_options", "new_options", "expected_total"),
    [
        (_options("0.10"), _options("0.20"), Decimal(2)),
        (
            _options("0.10"),
            _options("0.20", "2026-05-01"),
            Decimal(2),
        ),
        (
            _options("0.10"),
            _options(None, "2026-05-01", enabled=False),
            Decimal(),
        ),
        (
            _options(None, "2026-05-01", enabled=False),
            _options("0.20", "2026-05-01", enabled=True),
            Decimal(2),
        ),
    ],
)
async def test_covered_options_updates_do_not_fetch_usage(
    old_options: dict[str, object],
    new_options: dict[str, object],
    expected_total: Decimal,
) -> None:
    """Rate, date, disable, and re-enable changes reprice locally."""
    coordinator = _coordinator(old_options)
    coordinator._async_update_data_locked = AsyncMock()

    await coordinator.async_apply_cost_options(new_options)

    coordinator.api.get_energy_usage.assert_not_awaited()
    coordinator._async_update_data_locked.assert_not_awaited()
    coordinator._async_get_historical_usage.assert_not_awaited()
    assert coordinator.cost_ledger.total("electric_serial") == expected_total
    coordinator.async_set_updated_data.assert_called_once()


async def test_local_reprice_marks_earliest_changed_row_and_only_imports_cost() -> None:
    """A covered rate edit dirties and imports cost without consumption work."""
    coordinator = _coordinator(_options("0.10"))
    coordinator.cost_ledger.acknowledge_cost_statistics("electric_serial", INTERVAL)

    await coordinator.async_apply_cost_options(_options("0.25"))

    batch = coordinator.cost_ledger.cost_statistics("electric_serial")
    assert batch is not None
    assert batch.dirty_from == INTERVAL
    coordinator._async_import_dirty_cost_statistics.assert_awaited_once_with(
        METER,
        "serial",
        "electric_serial",
    )
    coordinator.api.get_energy_usage.assert_not_awaited()


async def test_unacknowledged_import_remains_recoverable() -> None:
    """Queueing a local reprice does not prematurely clear its dirty marker."""
    coordinator = _coordinator(_options("0.10"))
    coordinator.cost_ledger.acknowledge_cost_statistics("electric_serial", INTERVAL)

    await coordinator.async_apply_cost_options(_options("0.30"))

    batch = coordinator.cost_ledger.cost_statistics("electric_serial")
    assert batch is not None
    assert batch.dirty_from == INTERVAL
    coordinator.cost_ledger._store.async_save.assert_awaited()


async def test_periodic_refresh_and_options_update_are_serialized() -> None:
    """A periodic refresh holds the same lock used by an options update."""
    coordinator = _coordinator(_options("0.10"))
    refresh_entered = asyncio.Event()
    release_refresh = asyncio.Event()

    async def _locked_refresh(
        _self: DukeEnergyCoordinator,
    ) -> dict[str, object]:
        refresh_entered.set()
        await release_refresh.wait()
        return {}

    coordinator._async_update_data_locked = MethodType(_locked_refresh, coordinator)
    refresh_task = asyncio.create_task(coordinator._async_update_data())
    await refresh_entered.wait()
    options_task = asyncio.create_task(
        coordinator.async_apply_cost_options(_options("0.20"))
    )
    await asyncio.sleep(0)

    assert not options_task.done()
    assert coordinator.rate_provider.rate_at("ELECTRIC", INTERVAL) == Decimal("0.10")

    release_refresh.set()
    await refresh_task
    await options_task
    assert coordinator.rate_provider.rate_at("ELECTRIC", INTERVAL) == Decimal("0.20")


async def test_earlier_rate_fetches_only_missing_covered_range() -> None:
    """An earlier rate fetches only the gap before contiguous coverage."""
    coordinator = _coordinator(
        _options("0.10", "2026-04-01"),
        covered_from=date(2026, 4, 1),
    )
    coordinator._async_get_historical_usage.return_value = {
        datetime(2026, 3, 1, tzinfo=UTC): {"energy": 4}
    }

    await coordinator.async_apply_cost_options(_options("0.20", "2026-03-01"))

    coordinator._async_get_historical_usage.assert_awaited_once_with(
        METER,
        date(2026, 3, 1),
        date(2026, 3, 31),
    )
    coordinator.api.get_energy_usage.assert_not_awaited()
    assert coordinator.cost_ledger.history_covered_from("electric_serial") == date(
        2026, 3, 1
    )


async def test_failed_missing_range_does_not_advance_coverage() -> None:
    """A failed bounded fetch leaves the durable coverage marker unchanged."""
    coordinator = _coordinator(
        _options("0.10", "2026-04-01"),
        covered_from=date(2026, 4, 1),
    )
    coordinator._async_get_historical_usage.return_value = None

    await coordinator.async_apply_cost_options(_options("0.20", "2026-03-01"))

    assert coordinator.cost_ledger.history_covered_from("electric_serial") == date(
        2026, 4, 1
    )


async def test_display_data_updates_immediately_after_reprice() -> None:
    """The coordinator publishes the new display-only monetary total."""
    coordinator = _coordinator(_options("0.10"))

    await coordinator.async_apply_cost_options(_options("0.40"))

    published = coordinator.async_set_updated_data.call_args.args[0]
    assert published["serial"]["total_cost"] == Decimal("4.00")


async def test_invalid_provider_does_not_replace_live_provider() -> None:
    """Invalid options fail before replacing the working rate provider."""
    coordinator = _coordinator(_options("0.10"))
    invalid = _options("not-a-decimal")

    with pytest.raises(InvalidOperation):
        await coordinator.async_apply_cost_options(invalid)

    assert coordinator.rate_provider.rate_at("ELECTRIC", INTERVAL) == Decimal("0.10")
