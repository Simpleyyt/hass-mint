import logging
import time
import json
import socket
import datetime
import asyncio

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

from homeassistant.core import HomeAssistant
from homeassistant.const import *
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers import device_registry as dr

import voluptuous as vol


SCAN_INTERVAL = datetime.timedelta(seconds=15)

DOMAIN = "mint"

SUPPORTED_DOMAINS = [
    "switch"
]

CONF_PHONE_NUM = "phone_num"
CONF_IP = "ip"
CONF_PORT = "port"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PHONE_NUM): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, hass_config: dict):
    hass.data.setdefault(DOMAIN, {})
    config = hass_config.get(DOMAIN) or {}
    hass.data[DOMAIN]['config'] = config
    hass.data[DOMAIN].setdefault(CONF_DEVICES, {})
    hass.data[DOMAIN].setdefault('coordinators', {})
    hass.data[DOMAIN].setdefault('add_entities', {})
    gateway = MintGateway(hass, config)
    coordinator = MintCoordinator(gateway)
    hass.data[DOMAIN]['coordinators'][coordinator.name] = coordinator
    gateway.getip()
    await coordinator.async_config_entry_first_refresh()
    for platform in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(platform, DOMAIN, {}, config)
        )
    return True


async def async_setup_gateway(hass: HomeAssistant):
    for coordinator in hass.data[DOMAIN]['coordinators'].values():
        coordinator.update_entities()


class MintGateway:
    KEY =  b'(Mint@093$MingTe'
    IV = b'\x3d\xaf\xba\x42\x9d\x9e\xb4\x30\xb4\x22\xda\x80\x2c\x9f\xac\x41'
    BROADCAST_UDP_IP = "<broadcast>"
    BROADCAST_UDP_PORT = 11411
    BUFFER_SIZE = 4096
    TIMEOUT = 5

    def __init__(self, hass: HomeAssistant, config: dict):
        self._config = config
        self.hass = hass
        self.cipher = AES.new(self.KEY, AES.MODE_CBC, self.IV)

    def aes_encode(self, plaintext):
        _LOGGER.debug(plaintext)
        padded_plaintext = pad(plaintext.encode(), AES.block_size)
        cipher = AES.new(self.KEY, AES.MODE_CBC, self.IV)
        ciphertext = cipher.encrypt(padded_plaintext)
        ciphertext_bas64 = base64.b64encode(ciphertext).decode()
        return b'MINT' + len(ciphertext_bas64).to_bytes(2, byteorder='big') + ciphertext_bas64.encode()

    def aes_decode(self, ciphertext):
        _LOGGER.debug('Decode ciphertext %s', ciphertext)
        if ciphertext[:4] != b'MINT':
            raise RuntimeError('Wrong cipher text format!')
        payload = ciphertext[6:]
        cipher = AES.new(self.KEY, AES.MODE_CBC, self.IV)
        decrypted_padded_plaintext = cipher.decrypt(base64.b64decode(payload))
        plaintext = unpad(decrypted_padded_plaintext, AES.block_size)
        return plaintext.decode()

    def getip(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", self.BROADCAST_UDP_PORT))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(self.TIMEOUT)
        cmd = {
            "Command": "getip",
            "phoneNum": self._config.get(CONF_PHONE_NUM),
            "UsrDataSN": str(int(time.time() * 1000))
        }
        ciphertext = self.aes_encode(json.dumps(cmd))
        _LOGGER.error('Mint getip request %s %s', json.dumps(cmd), ciphertext)
        sock.sendto(ciphertext, (self.BROADCAST_UDP_IP, self.BROADCAST_UDP_PORT))
        while True:
            data, addr = sock.recvfrom(self.BUFFER_SIZE)
            if data != ciphertext:
                rsp = json.loads(self.aes_decode(data))
                self._config[CONF_IP] = rsp['ip']
                self._config[CONF_PORT] = rsp['port']
                _LOGGER.error('Mint getip response %s', rsp)
                break
        sock.close()

    async def send_command(self, cmd):
        retry = False
        try:
            code, data = await self._send_command(cmd)
            if code != 0 or not data:
                retry = True
        except Exception as e:
            _LOGGER.error("Send command exception %s", e)
            retry = True
        if retry:
            self.getip()
            code, data = await self._send_command(cmd)
        return code, data
    
    async def _send_command(self, cmd):
        cmd = cmd | {
            "phoneNum": self._config.get(CONF_PHONE_NUM),
            "UsrDataSN": str(int(time.time() * 1000))
        }
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.TIMEOUT)
        _LOGGER.error('connect %s %s', self.ip, self.port)
        sock.connect((self.ip, self.port))
        sock.send(json.dumps(cmd).encode())
        await asyncio.sleep(0.5)
        rsp = sock.recv(self.BUFFER_SIZE).decode()
        sock.close()
        _LOGGER.error('Mint %s response %s', cmd['Command'], rsp)
        dec = json.JSONDecoder()
        rsp_code, index = dec.raw_decode(rsp)
        code = int(rsp_code['returnCode'])
        if code == 0:
            data, index = dec.raw_decode(rsp[index:])
        else:
            _LOGGER.error('Mint %s response %s', cmd['Command'], rsp)
        return code, data
    
    async def getallstatus(self):
        code, data = await self.send_command({"Command": "getallstatus"})
        return data
    
    async def initial(self):
        code, data = await self.send_command({"Command": "initial"})
        return data

    async def trigger(self, action, unique_id, ccmdid):
        code, data = await self.send_command({
            "Command": [
                {
                    "cmd": [{ "action": action }],
                    "sourceId": "00fefc",
                    "destinationId": unique_id,
                    "ccmdid": ccmdid
                }]
            })
        return data

    @property
    def ip(self):
        return self._config.get(CONF_IP) or ''

    @property
    def port(self):
        return int(self._config.get(CONF_PORT)) or 11315


    @property
    def update_interval(self):
        return self._config.get(CONF_SCAN_INTERVAL) or SCAN_INTERVAL


class MintCoordinator(DataUpdateCoordinator):
    def __init__(self, gateway: MintGateway):
        super().__init__(
            gateway.hass,
            _LOGGER,
            name=f'{DOMAIN}',
            update_interval=gateway.update_interval
        )
        self.gateway = gateway

    async def _async_update_data(self):
        data = await self.gateway.initial()
        status = await self.gateway.getallstatus()
        for room in data['rootJson']['rooms']:
            for device_data in room['rdevices']:
                device_status = None
                for dvc in status['devices']:
                    if dvc['sourceId'] == device_data['did']:
                        device_status = dvc
                        break
                device = self.hass.data[DOMAIN][CONF_DEVICES].get(device_data['did'])
                if device:
                    device.update_data(device_data, device_status)
                else:
                    device = MintDevice(self, device_data, device_status)
                    self.hass.data[DOMAIN][CONF_DEVICES][device.did] = device
                device.update_entities()
        return self.hass.data[DOMAIN][CONF_DEVICES]

    def update_entities(self):
        for did, device in self.hass.data[DOMAIN][CONF_DEVICES].items():
            device.update_entities()


class MintDevice:
    def __init__(self, coordinator: MintCoordinator, data: dict, status: dict):
        self.entities = {}
        self.coordinator = coordinator
        self.update_data(data, status)

    def update_data(self, data: dict, status: dict):
        self.data = data
        self.status = status

    @property
    def name(self):
        return self.data.get('dname')

    @property
    def did(self):
        return self.data.get('did')

    def update_entities(self):
        from .switch import MintSwitchEntity
        for channel in self.data['channel']:
            action = None
            if self.status:
                for report in self.status['report']:
                    if report['cid'] == channel['cid']:
                        action = report['action']
                        break
            entity = self.entities.get(channel['cid'])
            if entity:
                entity.update_data(channel, action)
            else:
                if channel['subtype'] == 'switch':
                    add = self.coordinator.hass.data[DOMAIN]['add_entities'].get('switch')
                    if add:
                        entity = MintSwitchEntity(self, channel, action)
                        add([entity])
                self.entities[channel['cid']] = entity
            

class MintEntity(CoordinatorEntity):
    def __init__(self, device: MintDevice, data: dict, status: str):
        self.coordinator = device.coordinator
        CoordinatorEntity.__init__(self, self.coordinator)
        self._device = device
        self.update_data(data, status)

    def update_data(self, data: dict, status: str):
        self.data = data
        self.status = status
        self._attr_name = self.data['cname']
        self._attr_device_id = f'{self.data["subtype"]}_{self.data["ccmdid"]}'
        self._attr_unique_id = self.data['ccmdid']
        self._attr_device_info = {
            'identifiers': {(DOMAIN, self._attr_device_id)},
            'name': self._device.name,
            'model': self._device.data['dtype'],
            'manufacturer': self._device.data['dfactory'],
            'sw_version': self._device.data['dversion'],
        }
