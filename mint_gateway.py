
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
    TIMEOUT = 15

    def __init__(self, phone_number):
        self.phone_number = phone_number
        self.ip = None
        self.port = None
        self.cipher = AES.new(self.KEY, AES.MODE_CBC, self.IV)

    def aes_encode(self, plaintext):
        LOGGER.debug(plaintext)
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

    def getip(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("0.0.0.0", self.BROADCAST_UDP_PORT))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(self.TIMEOUT)
            cmd = {
                "Command": "getip",
                "phoneNum": self.phone_number,
                "UsrDataSN": str(int(time.time() * 1000))
            }
            ciphertext = self.aes_encode(json.dumps(cmd))
            LOGGER.error('Mint getip request %s %s', json.dumps(cmd), ciphertext)
            sock.sendto(ciphertext, (self.BROADCAST_UDP_IP, self.BROADCAST_UDP_PORT))
            data, addr = sock.recvfrom(self.BUFFER_SIZE)
            if data == ciphertext:
                data, addr = sock.recvfrom(self.BUFFER_SIZE)
        finally:
            sock.close()
        LOGGER.error(data)
        rsp = json.loads(self.aes_decode(data))
        self.ip = rsp['ip']
        self.port = int(rsp['port'])
        LOGGER.error('Mint getip response %s', rsp)

    async def send_command(self, cmd):
        retry = False
        if not self.ip or not self.port:
            self.getip()
        try:
            code, data = await self._send_command(cmd)
            if code != 0 or not data:
                retry = True
        except Exception as e:
            LOGGER.error("Send command exception %s", e)
            retry = True
        if retry:
            self.getip()
            code, data = await self._send_command(cmd)
        return code, data
    
    async def _send_command(self, cmd):
        cmd = cmd | {
            "phoneNum": self.phone_number,
            "UsrDataSN": str(int(time.time() * 1000))
        }
        data = None
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.TIMEOUT)
            LOGGER.error('connect %s %s', self.ip, self.port)
            sock.connect((self.ip, self.port))
            sock.send(json.dumps(cmd).encode())
            rsp = sock.recv(self.BUFFER_SIZE).decode()
            LOGGER.error('Mint %s response %s', cmd['Command'], rsp)
            dec = json.JSONDecoder()
            rsp_code, index = dec.raw_decode(rsp)
            code = int(rsp_code['returnCode'])
            if code != 0:
                LOGGER.error('Mint %s response %s', cmd['Command'], rsp)
                sock.close()
                return code, data
            if index == len(rsp):
                rsp = sock.recv(self.BUFFER_SIZE).decode()
                LOGGER.error('Mint %s response %s', cmd['Command'], rsp)
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