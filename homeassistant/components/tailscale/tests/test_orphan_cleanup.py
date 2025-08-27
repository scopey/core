import pytest
from unittest.mock import MagicMock, patch

from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

@pytest.mark.asyncio
async def test_orphan_removal(hass):
    # Setup: registry, add device and entity
    device_registry = async_get_device_registry(hass)
    entity_registry = async_get_entity_registry(hass)
    config_entry_id = "abc123"

    # Add a present and an orphan device
    dev1 = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={("tailscale", "kept_device")},
        name="test_kept"
    )
    orphan_dev = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={("tailscale", "orphan_device")},
        name="test_orphan"
    )
    entity_registry.async_get_or_create(
        "sensor", "tailscale", "ent_kept", device_id=dev1.id
    )
    orphan_ent = entity_registry.async_get_or_create(
        "sensor", "tailscale", "ent_orphan", device_id=orphan_dev.id
    )

    # Patch the Tailscale.devices() to only return "kept_device"
    with patch("homeassistant.components.tailscale.coordinator.Tailscale.devices",
               return_value={"kept_device": MagicMock()}):
        from homeassistant.components.tailscale.coordinator import TailscaleDataUpdateCoordinator
        coordinator = TailscaleDataUpdateCoordinator(
            hass, MagicMock(entry_id=config_entry_id, data={"api_key":"x","tailnet":"x"})
        )
        await coordinator._async_update_data()

    # Validate: orphan device and entity are gone, valid ones stay
    assert device_registry.async_get(orphan_dev.id) is None
    assert entity_registry.async_get(orphan_ent.entity_id) is None
    assert device_registry.async_get(dev1.id) is not None

