"""Example switch platform."""

from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.switch import (
    SwitchEntity,
    DOMAIN as ENTITY_DOMAIN,
)

from . import (
    DOMAIN,
    MintEntity,
    async_setup_gateway,
    _LOGGER
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    cfg = {**config_entry.data, **config_entry.options}
    await async_setup_platform(hass, cfg, async_setup_platform, async_add_entities)

async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    hass.data[DOMAIN]['add_entities'][ENTITY_DOMAIN] = async_add_entities
    await async_setup_gateway(hass)


class MintSwitchEntity(MintEntity, SwitchEntity):
    @property
    def is_on(self):
        return self._attr_state == 'on'
    @property
    def hidden(self):
        return False

    async def async_turn_switch(self, on=True, **kwargs):
        data = await self.coordinator.gateway.trigger('open' if on else 'close', self._device.did, self.data['ccmdid'])
        if data:
            self.status = 'open' if on else 'close'
            self.async_write_ha_state()
            self._handle_coordinator_update()
            return True
        return False

    async def async_turn_on(self, **kwargs):
        return await self.async_turn_switch(True)

    async def async_turn_off(self, **kwargs):
        return await self.async_turn_switch(False)

    def _handle_coordinator_update(self):
        self._attr_state = 'off'
        if self.status == 'open':
            self._attr_state = 'on'
        elif self.status == 'close':
            self._attr_state = 'off'
        self.async_write_ha_state()