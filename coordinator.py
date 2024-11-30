from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import *
from .mint_gateway import MintGateway

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
        self.gateway = MintGateway(phone_number)
        self.gateway.getip()

    async def _async_update_data(self):
        LOGGER.debug("Mint: update data")
        devices = await self.gateway.initial()
        status = await self.gateway.getallstatus()
        data = {
            "devices": devices,
            "status": status
        }
        return data
