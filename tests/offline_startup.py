"""Offline setup regressions using explicit HA lifecycle doubles, no services."""

# Standalone unittest avoids installing pytest or HA. Named tests describe behavior.
# ruff: noqa: D102, D103, D107, PT009, PT027
import asyncio
import importlib
import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class NotReadyError(Exception):
    """HA retryable setup error double."""


class AuthFailedError(Exception):
    """HA reauthentication error double."""


class ResponseError(Exception):
    """HTTP response error double."""

    def __init__(self, status: int) -> None:
        self.status = status


def module(name: str, **values: object) -> ModuleType:
    obj = ModuleType(name)
    obj.__dict__.update(values)
    sys.modules[name] = obj
    return obj


# Only framework/client boundaries are doubled; the integration setup is real.
module("homeassistant", __path__=[])
module("homeassistant.const", Platform=SimpleNamespace(SENSOR="sensor"))
module(
    "homeassistant.exceptions",
    ConfigEntryNotReady=NotReadyError,
    ConfigEntryAuthFailed=AuthFailedError,
)
module(
    "aiohttp", ClientConnectionError=ConnectionError, ClientResponseError=ResponseError
)
CLIENT = module("aiodukeenergy", DukeEnergy=MagicMock())
OAUTH = module(
    "homeassistant.helpers.config_entry_oauth2_flow",
    async_register_implementation=MagicMock(),
    async_get_config_entry_implementation=AsyncMock(),
    OAuth2Session=MagicMock(),
)
module(
    "homeassistant.helpers",
    aiohttp_client=SimpleNamespace(async_get_clientsession=MagicMock()),
    config_entry_oauth2_flow=OAUTH,
)
module("custom_components.duke_energy.api", DukeEnergyAuth=MagicMock())
COORD = module(
    "custom_components.duke_energy.coordinator",
    DukeEnergyConfigEntry=object,
    DukeEnergyCoordinator=MagicMock(),
)
module(
    "custom_components.duke_energy.oauth", DukeEnergyOAuth2Implementation=MagicMock()
)
INTEGRATION = importlib.import_module("custom_components.duke_energy")


class Startup(unittest.IsolatedAsyncioTestCase):
    """Exercise the actual entry setup without HTTP, HA, or a database."""

    def setUp(self) -> None:
        self.events = []
        self.hass = SimpleNamespace(
            is_running=True,
            async_add_executor_job=AsyncMock(),
            config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()),
        )
        self.entry = SimpleNamespace(
            data={"token": True},
            async_on_unload=MagicMock(),
            add_update_listener=MagicMock(),
        )
        self.session = SimpleNamespace(async_ensure_token_valid=AsyncMock())
        OAUTH.OAuth2Session.return_value = self.session
        self.coord = SimpleNamespace(
            async_initialize_costs=AsyncMock(),
            async_config_entry_first_refresh=AsyncMock(),
        )
        COORD.DukeEnergyCoordinator.return_value = self.coord
        for name, fn in [
            ("auth", self.session.async_ensure_token_valid),
            ("ledger", self.coord.async_initialize_costs),
            ("refresh", self.coord.async_config_entry_first_refresh),
            ("sensors", self.hass.config_entries.async_forward_entry_setups),
        ]:

            async def call(
                *_args: object, label: str = name, **_kwargs: object
            ) -> None:
                self.events.append(label)

            fn.side_effect = call
        # Runtime provenance is tested independently, not waived in production.
        if hasattr(INTEGRATION, "verify_installed_client"):
            p = patch.object(INTEGRATION, "verify_installed_client")
            p.start()
            self.addCleanup(p.stop)

    async def test_boot_defers_before_auth_or_statistics(self) -> None:
        self.hass.is_running = False
        with self.assertRaises(NotReadyError):
            await INTEGRATION.async_setup_entry(self.hass, self.entry)
        self.assertEqual(self.events, [])
        self.assertFalse(hasattr(self.entry, "runtime_data"))

    async def test_retry_after_running_uses_unchanged_setup(self) -> None:
        self.hass.is_running = False
        with self.assertRaises(NotReadyError):
            await INTEGRATION.async_setup_entry(self.hass, self.entry)
        self.hass.is_running = True
        self.assertTrue(await INTEGRATION.async_setup_entry(self.hass, self.entry))
        self.assertEqual(self.events, ["auth", "ledger", "refresh", "sensors"])

    async def test_unverified_client_never_authenticates(self) -> None:
        self.hass.async_add_executor_job.side_effect = (
            INTEGRATION.ClientUnavailableError("fixture mismatch")
        )
        with self.assertRaises(NotReadyError):
            await INTEGRATION.async_setup_entry(self.hass, self.entry)
        self.assertEqual(self.events, [])

    async def test_running_preserves_first_refresh_and_sensor_order(self) -> None:
        self.assertTrue(await INTEGRATION.async_setup_entry(self.hass, self.entry))
        self.assertEqual(self.events, ["auth", "ledger", "refresh", "sensors"])
        self.assertIs(self.entry.runtime_data, self.coord)

    async def test_sensors_wait_for_actual_first_refresh(self) -> None:
        ready = asyncio.Event()
        entered = asyncio.Event()

        async def refresh() -> None:
            entered.set()
            await ready.wait()

        self.coord.async_config_entry_first_refresh.side_effect = refresh
        task = asyncio.create_task(INTEGRATION.async_setup_entry(self.hass, self.entry))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            self.hass.config_entries.async_forward_entry_setups.assert_not_awaited()
            ready.set()
            self.assertTrue(await asyncio.wait_for(task, 1))
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_timeout_remains_retryable(self) -> None:
        self.session.async_ensure_token_valid.side_effect = TimeoutError
        with self.assertRaises(NotReadyError):
            await INTEGRATION.async_setup_entry(self.hass, self.entry)
        self.coord.async_config_entry_first_refresh.assert_not_awaited()

    async def test_invalid_credentials_still_require_reauthentication(self) -> None:
        self.session.async_ensure_token_valid.side_effect = ResponseError(401)
        with self.assertRaises(AuthFailedError):
            await INTEGRATION.async_setup_entry(self.hass, self.entry)

    async def test_refresh_failure_never_registers_sensors(self) -> None:
        self.coord.async_config_entry_first_refresh.side_effect = NotReadyError(
            "fixture unavailable"
        )
        with self.assertRaises(NotReadyError):
            await INTEGRATION.async_setup_entry(self.hass, self.entry)
        self.hass.config_entries.async_forward_entry_setups.assert_not_awaited()


class Manifest(unittest.TestCase):
    """Keep dependency handling outside the startup package manager."""

    def test_boot_does_not_invoke_an_installer(self) -> None:
        manifest = json.loads(
            (ROOT / "custom_components/duke_energy/manifest.json").read_text()
        )
        self.assertEqual(manifest["requirements"], [])


class Dependency(unittest.TestCase):
    """Verify source provenance and corruption fail closed, without imports."""

    def setUp(self) -> None:
        self.dep = importlib.import_module(
            "custom_components.duke_energy.client_dependency"
        )
        self.lock = json.loads(
            (ROOT / "custom_components/duke_energy/client_lock.json").read_text()
        )
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        source = Path(os.environ["DUKE_PINNED_SOURCE"])
        for relative in self.lock["sha256"]:
            dest = self.base / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Fixtures normalize a Windows checkout to Git's LF source bytes.
            dest.write_bytes(
                (source / Path(relative).relative_to("aiodukeenergy"))
                .read_bytes()
                .replace(b"\r\n", b"\n")
            )
        self.provenance = {
            "url": self.lock["repository"],
            "vcs_info": {"vcs": "git", "commit_id": self.lock["commit"]},
        }
        self.dist = SimpleNamespace(
            version=self.lock["version"],
            read_text=lambda _: json.dumps(self.provenance),
            locate_file=lambda relative: self.base / relative,
        )
        self.origin = str(self.base / "aiodukeenergy/__init__.py")
        for target, value in [
            ("metadata.distribution", self.dist),
            ("util.find_spec", SimpleNamespace(origin=self.origin)),
        ]:
            p = patch(
                "custom_components.duke_energy.client_dependency." + target,
                return_value=value,
            )
            p.start()
            self.addCleanup(p.stop)

    def test_exact_cached_fork_passes_without_import(self) -> None:
        self.dep.verify_installed_client()

    def test_wrong_version_is_rejected(self) -> None:
        self.dist.version = "0.0.0"
        with self.assertRaises(self.dep.ClientUnavailableError):
            self.dep.verify_installed_client()

    def test_malformed_vcs_metadata_is_rejected(self) -> None:
        self.provenance["vcs_info"] = []
        with self.assertRaises(self.dep.ClientUnavailableError):
            self.dep.verify_installed_client()

    def test_wrong_commit_is_rejected(self) -> None:
        self.provenance["vcs_info"]["commit_id"] = "0" * 40
        with self.assertRaises(self.dep.ClientUnavailableError):
            self.dep.verify_installed_client()

    def test_wrong_repository_is_rejected(self) -> None:
        self.provenance["url"] = "https://example.invalid/other.git"
        with self.assertRaises(self.dep.ClientUnavailableError):
            self.dep.verify_installed_client()

    def test_same_version_with_changed_source_is_rejected(self) -> None:
        (self.base / "aiodukeenergy/auth0.py").write_text("fixture changed")
        with self.assertRaises(self.dep.ClientUnavailableError):
            self.dep.verify_installed_client()

    def test_missing_source_is_rejected(self) -> None:
        (self.base / "aiodukeenergy/auth0.py").unlink()
        with self.assertRaises(self.dep.ClientUnavailableError):
            self.dep.verify_installed_client()

    def test_missing_provenance_is_rejected(self) -> None:
        self.dist.read_text = lambda _: None
        with self.assertRaises(self.dep.ClientUnavailableError):
            self.dep.verify_installed_client()

    def test_shadowed_import_is_rejected(self) -> None:
        with (
            patch.object(
                self.dep.util,
                "find_spec",
                return_value=SimpleNamespace(origin=str(self.base / "other.py")),
            ),
            self.assertRaises(self.dep.ClientUnavailableError),
        ):
            self.dep.verify_installed_client()

    def test_missing_distribution_is_rejected(self) -> None:
        with (
            patch.object(
                self.dep.metadata,
                "distribution",
                side_effect=self.dep.metadata.PackageNotFoundError,
            ),
            self.assertRaises(self.dep.ClientUnavailableError),
        ):
            self.dep.verify_installed_client()


class Statistics(unittest.TestCase):
    """Exercise real ledger arithmetic and durable acknowledgement rules."""

    def setUp(self) -> None:
        module("homeassistant.helpers.storage", Store=MagicMock())
        self.cost = importlib.import_module("custom_components.duke_energy.cost")
        self.ledger = object.__new__(self.cost.CostLedger)
        self.ledger._data = {"meters": {}}
        self.ledger._dirty = False
        self.when = datetime(2026, 1, 1, tzinfo=UTC)
        self.provider = self.cost.ManualRateProvider(
            {
                "cost_tracking": {
                    "ELECTRIC": {
                        "enabled": True,
                        "rates": [{"effective_date": "2026-01-01", "rate": "0.1"}],
                    }
                }
            }
        )

    def test_repeated_first_refresh_does_not_double_count(self) -> None:
        for _ in range(2):
            result = self.ledger.update(
                "electric_fixture",
                "ELECTRIC",
                {self.when: {"energy": 10}},
                self.provider,
            )
        self.assertEqual(result, Decimal("1.0"))
        self.assertEqual(
            len(self.ledger.cost_statistics("electric_fixture").statistics), 1
        )

    def test_pending_statistics_survive_snapshot_and_restore(self) -> None:
        self.ledger.update(
            "electric_fixture", "ELECTRIC", {self.when: {"energy": 10}}, self.provider
        )
        restored = object.__new__(self.cost.CostLedger)
        restored.restore(self.ledger.snapshot())
        batch = restored.cost_statistics("electric_fixture")
        self.assertEqual(batch.statistics[0].cumulative_cost, Decimal("1.0"))
        self.assertIsNotNone(self.ledger.cost_statistics("electric_fixture"))
        restored.acknowledge_cost_statistics("electric_fixture", batch.dirty_from)
        self.assertIsNone(restored.cost_statistics("electric_fixture"))
        self.assertIsNotNone(self.ledger.cost_statistics("electric_fixture"))


if __name__ == "__main__":
    unittest.main()
