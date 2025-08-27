"""DataUpdateCoordinator for the Tailscale integration."""

from __future__ import annotations

from tailscale import Device, Tailscale, TailscaleAuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import CONF_TAILNET, DOMAIN, LOGGER, SCAN_INTERVAL

import logging

class TailscaleDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """The Tailscale Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Tailscale coordinator."""
        session = async_get_clientsession(hass)
        self.tailscale = Tailscale(
            session=session,
            api_key=config_entry.data[CONF_API_KEY],
            tailnet=config_entry.data[CONF_TAILNET],
        )

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch devices from Tailscale and globally remove orphaned registry/device entries."""
        try:
            devices = await self.tailscale.devices()
        except TailscaleAuthenticationError as err:
            raise ConfigEntryAuthFailed from err

        device_registry = async_get_device_registry(self.hass)
        entity_registry = async_get_entity_registry(self.hass)
        logger = logging.getLogger(__name__)

        current_ts_ids = set(devices.keys())

        # Global clean: remove any Tailscale device not in Tailscale API
        for device in list(device_registry.devices.values()):
            device_ts_ids = [idval for (domain, idval) in device.identifiers if domain == "tailscale"]
            orphan = False
            if not device_ts_ids:
                orphan = True
            else:
                for ts_id in device_ts_ids:
                    if ts_id not in current_ts_ids:
                        orphan = True
            if orphan:
                logger.info(f"Pruning orphan device: name={device.name}, id={device.id}, identifiers={device.identifiers}")
                for entity in list(entity_registry.entities.values()):
                    if entity.device_id == device.id:
                        logger.info(f"  Removing orphan entity: {entity.entity_id}")
                        entity_registry.async_remove(entity.entity_id)
                device_registry.async_remove_device(device.id)
                logger.info(f"  Device {device.name} [{device.id}] removed from HA registry.")

        return devices

