
import json
import socket
import asyncio
import base64
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from .const import *

class MintGateway:
    KEY =  b'(Mint@093$MingTe'
    IV = b'\x3d\xaf\xba\x42\x9d\x9e\xb4\x30\xb4\x22\xda\x80\x2c\x9f\xac\x41'
    BROADCAST_UDP_IP = "<broadcast>"
    BROADCAST_UDP_PORT = 11411
    BUFFER_SIZE = 4096
    TIMEOUT = 30

    def __init__(self, hass, phone_number):
        self.hass = hass
        self.phone_number = phone_number
        self.ip = None
        self.port = None
        self.cipher = AES.new(self.KEY, AES.MODE_CBC, self.IV)
        self.udp =  socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("0.0.0.0", self.BROADCAST_UDP_PORT))
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp.settimeout(self.TIMEOUT)
        self.udp.setblocking(False)

    def aes_encode(self, plaintext):
        LOGGER.debug('Encode %s', plaintext)
        padded_plaintext = pad(plaintext.encode(), AES.block_size)
        cipher = AES.new(self.KEY, AES.MODE_CBC, self.IV)
        ciphertext = cipher.encrypt(padded_plaintext)
        ciphertext_bas64 = base64.b64encode(ciphertext).decode()
        return b'MINT' + len(ciphertext_bas64).to_bytes(2, byteorder='big') + ciphertext_bas64.encode()

    def aes_decode(self, ciphertext):
        LOGGER.debug('Decode ciphertext %s', ciphertext)
        if ciphertext[:4] != b'MINT':
            raise RuntimeError('Wrong cipher text format!')
        payload = ciphertext[6:]
        cipher = AES.new(self.KEY, AES.MODE_CBC, self.IV)
        decrypted_padded_plaintext = cipher.decrypt(base64.b64decode(payload))
        plaintext = unpad(decrypted_padded_plaintext, AES.block_size)
        return plaintext.decode()

    async def getip(self):
        LOGGER.info("Mint: getip")
        try:
            loop = asyncio.get_event_loop()
            cmd = {
                "Command": "getip",
                "phoneNum": self.phone_number,
                "UsrDataSN": str(int(time.time() * 1000))
            }
            ciphertext = self.aes_encode(json.dumps(cmd))
            LOGGER.info('Mint getip request %s %s', json.dumps(cmd), ciphertext)
            await loop.sock_sendto(self.udp, ciphertext, (self.BROADCAST_UDP_IP, self.BROADCAST_UDP_PORT))
            data, addr = await asyncio.wait_for(loop.sock_recvfrom(self.udp, self.BUFFER_SIZE), self.TIMEOUT)
            if data == ciphertext:
                data, addr = await asyncio.wait_for(loop.sock_recvfrom(self.udp, self.BUFFER_SIZE), self.TIMEOUT)
            LOGGER.info("Mint getip recv data %s", data)
            rsp = json.loads(self.aes_decode(data))
            self.ip = rsp['ip']
            self.port = int(rsp['port'])
            LOGGER.info('Mint getip response %s', rsp)
        except Exception as e:
            LOGGER.error("Mint getip error %s", e)

    async def send_command(self, cmd):
        error = False
        try:
            code, data = await self._send_command(cmd)
            if code != 0 or not data:
                error = True
        except Exception as e:
            LOGGER.error("Send command exception %s", e)
            error = True
            raise e
        return code, data
    
    async def _send_command(self, cmd):
        cmd = cmd | {
            "phoneNum": self.phone_number,
            "UsrDataSN": str(int(time.time() * 1000))
        }
        data = None
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setblocking(False)
            loop = asyncio.get_event_loop()
            sock.settimeout(self.TIMEOUT)
            LOGGER.info('Mint connect %s %s', self.ip, self.port)
            await loop.sock_connect(sock, (self.ip, self.port))
            await loop.sock_sendall(sock, json.dumps(cmd).encode())
            rsp = (await asyncio.wait_for(loop.sock_recv(sock, self.BUFFER_SIZE), self.TIMEOUT)).decode()
            LOGGER.info('Mint %s response %s', cmd['Command'], rsp)
            dec = json.JSONDecoder()
            rsp_code, index = dec.raw_decode(rsp)
            code = int(rsp_code['returnCode'])
            if code != 0:
                LOGGER.error('Mint %s response %s', cmd['Command'], rsp)
                sock.close()
                return code, data
            if index == len(rsp):
                await asyncio.sleep(0.5)
                rsp = (await asyncio.wait_for(loop.sock_recv(sock, self.BUFFER_SIZE), self.TIMEOUT)).decode()
                LOGGER.info('Mint %s response %s', cmd['Command'], rsp)
                index = 0
        finally:
            sock.close()
        data, index = dec.raw_decode(rsp[index:])
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