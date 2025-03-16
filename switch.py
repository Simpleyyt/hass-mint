import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.switch import (
    SwitchEntity,
    DOMAIN as ENTITY_DOMAIN,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import *

async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    coordinator = hass.data[DOMAIN][CONF_COORDINATOR]
    switches = []
    for room in coordinator.data['devices']['rootJson']['rooms']:
        for rdevice in room['rdevices']:
            for channel in rdevice['channel']:
                if channel['subtype'] == 'switch':
                    switches.append(MintSwitch(coordinator, room['rid'], rdevice['did'], channel['cid']))
    async_add_entities(switches)


class MintSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, rid, did, cid):
        super().__init__(coordinator)
        self.rid = rid
        self.did = did
        self.cid = cid
    
    @property
    def is_on(self):
        return self.channel_status['action'] == 'open'

    @property
    def hidden(self):
        return False

    async def async_turn_switch(self, on=True, **kwargs):
        succ = await self.coordinator.gateway.trigger('open' if on else 'close', self.did, self.channel_data['ccmdid'])
        if succ:
            self.channel_status['action'] = 'open' if on else 'close'
            self.async_write_ha_state()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        await self.async_turn_switch(True)

    async def async_turn_off(self, **kwargs):
        await self.async_turn_switch(False)
    
    @property
    def room_data(self):
        for room in self.coordinator.data['devices']['rootJson']['rooms']:
            if self.rid == room['rid']:
                return room

    @property
    def device_data(self):
        for device in self.room_data['rdevices']:
            if self.did == device['did']:
                return device

    @property
    def channel_data(self):
        for channel in self.device_data['channel']:
            if self.cid == channel['cid']:
                return channel

    @property
    def device_status(self):
        for device in self.coordinator.data['status']['devices']:
            if self.did == device['sourceId']:
                return device
            
    @property
    def channel_status(self):
        for report in self.device_status['report']:
            if report['cid'] == self.cid:
                return report

    @property
    def unique_id(self) -> str:
        return self.channel_data['ccmdid']
    
    @property
    def name(self) -> str:
        return self.channel_data['cname']
    
    @property
    def device_id(self) -> str:
        return f'{self.channel_data["subtype"]}_{self.channel_data["ccmdid"]}'

    @property
    def device_info(self) -> str:
        return  {
            'identifiers': {(DOMAIN, self.device_id)},
            'name': self.device_data['name'],
            'model': self.device_data['dtype'],
            'manufacturer': self.device_data['dfactory'],
            'sw_version': self.device_data['dversion'],
        }

    @property
    def available(self) -> bool:
        return True