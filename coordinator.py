from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import *
from .mint_gateway import MintGateway
import time

class MintCoordinator(DataUpdateCoordinator):
    data :dict

    def __init__(self, hass, config):
        phone_number = config.get(CONF_PHONE_NUM)
        update_interval = config.get(CONF_SCAN_INTERVAL) or DEFAULT_SCAN_INTERVAL
        super().__init__(
            hass,
            LOGGER,
            name=f'{DOMAIN}',
            update_interval=update_interval
        )
        self.last_getip_time = None
        self.gateway = MintGateway(hass, phone_number)

    async def _async_update_data(self):
        LOGGER.debug("Mint: update data")
        current_time = time.time()
        if self.last_getip_time is None or current_time - self.last_getip_time > GETIP_INTERVAL_S:
            await self.gateway.getip()
            self.last_getip_time = current_time
        devices = await self.gateway.initial()
        status = await self.gateway.getallstatus()
        data = {
            "devices": devices,
            "status": status
        }
        return data
