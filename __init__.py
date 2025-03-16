from homeassistant.helpers.discovery import async_load_platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import *
from .coordinator import MintCoordinator
    
def hook_homekit():
    from homeassistant.components.homekit.type_thermostats import Thermostat
    origin_set_chars = Thermostat._set_chars
    def new_set_chars(self, char_values, *args, **kwargs):
        LOGGER.debug(f"Hook homekit.Thermostat._set_chars")
        if (
            "TargetHeatingCoolingState" in char_values
            and char_values["TargetHeatingCoolingState"] == 0
        ):
            char_values = {"TargetHeatingCoolingState": 0}
        return origin_set_chars(self, char_values)
    Thermostat._set_chars = new_set_chars

async def async_setup(hass: HomeAssistant, hass_config: dict):
    hook_homekit()
    hass.data.setdefault(DOMAIN, {})
    config = hass_config.get(DOMAIN) or {}
    coordinator = MintCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][CONF_COORDINATOR] = coordinator
    for platform in SUPPORTED_DOMAINS:
        await async_load_platform(hass, platform, DOMAIN, {}, config)
    return True
