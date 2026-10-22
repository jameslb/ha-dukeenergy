"""The Duke Energy integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import ClientConnectionError, ClientResponseError
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .client_dependency import ClientUnavailableError, verify_installed_client
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import DukeEnergyConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: DukeEnergyConfigEntry) -> bool:
    """Set up Duke Energy from a config entry."""
    if not hass.is_running:
        message = "Waiting for Home Assistant startup before Duke setup"
        raise ConfigEntryNotReady(message)

    try:
        await hass.async_add_executor_job(verify_installed_client)
    except ClientUnavailableError as err:
        raise ConfigEntryNotReady(str(err)) from err

    # Never import or install an unverified replacement for the pinned client.
    from aiodukeenergy import DukeEnergy  # noqa: PLC0415

    from .api import DukeEnergyAuth  # noqa: PLC0415
    from .coordinator import DukeEnergyCoordinator  # noqa: PLC0415
    from .oauth import DukeEnergyOAuth2Implementation  # noqa: PLC0415

    # Register our OAuth implementation
    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        DukeEnergyOAuth2Implementation(hass),
    )

    # Check if this is an old entry that needs reauth
    if not entry.data.get("token"):
        msg = "Authentication method has changed. Please reauthenticate."
        raise ConfigEntryAuthFailed(msg)

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except (TimeoutError, ClientConnectionError) as err:
        message = "Duke Energy authentication service unavailable"
        raise ConfigEntryNotReady(message) from err
    except ClientResponseError as err:
        if err.status not in (400, 401):
            message = "Duke Energy authentication service temporarily unavailable"
            raise ConfigEntryNotReady(message) from err
        raise ConfigEntryAuthFailed from err
    except (KeyError, ValueError) as err:
        raise ConfigEntryAuthFailed from err

    auth = DukeEnergyAuth(aiohttp_client.async_get_clientsession(hass), session)
    client = DukeEnergy(auth)

    coordinator = DukeEnergyCoordinator(hass, client, entry)
    await coordinator.async_initialize_costs()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_options(
    _hass: HomeAssistant, entry: DukeEnergyConfigEntry
) -> None:
    """Apply cost options without reloading or fetching current usage."""
    await entry.runtime_data.async_apply_cost_options(entry.options)


async def async_migrate_entry(
    hass: HomeAssistant, entry: DukeEnergyConfigEntry
) -> bool:
    """Cannot migrate without reauth."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry, data={}, minor_version=1, version=2
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DukeEnergyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
