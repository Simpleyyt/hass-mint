
import datetime
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_SCAN_INTERVAL

DEFAULT_SCAN_INTERVAL = datetime.timedelta(seconds=15)

DEFAULT_PORT = "11315"

DOMAIN = "mint"

SUPPORTED_DOMAINS = [
    "switch"
]

CONF_PHONE_NUM = "phone_num"
CONF_COORDINATOR = 'coordinator'

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PHONE_NUM): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

LOGGER = logging.getLogger(__name__)

GETIP_INTERVAL_S = 60