from homeassistant.helpers.discovery import async_load_platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import *
from .coordinator import MintCoordinator


async def async_setup(hass: HomeAssistant, hass_config: dict):
    hass.data.setdefault(DOMAIN, {})
    config = hass_config.get(DOMAIN) or {}
    coordinator = MintCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][CONF_COORDINATOR] = coordinator
    for platform in SUPPORTED_DOMAINS:
        await async_load_platform(hass, platform, DOMAIN, {}, config)
    return True
