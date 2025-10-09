"""
Marstek Device API Client

This module provides communication with Marstek energy storage devices via UDP.

API Documentation: https://eu.hamedata.com/ems/resource/agreement/MarstekDeviceOpenApi.pdf

The ES (Energy System) component contains the device's basic power information 
and energy statistics, and can configure or monitor the device's operating status.
"""

import json 
import socket
import logging
import asyncio
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)


class _UDPClientProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue

    def datagram_received(self, data: bytes, addr):
        self.queue.put_nowait((data, addr))

    def error_received(self, exc: Exception):
        _LOGGER.debug("UDP protocol error received: %s", exc)


class MarstekApiClient:
    def __init__(self, ip: str, port: int, device_id: str, timeout: float = 5.0,
                 local_ip: str | None = None, local_port: int | None = None) -> None:
        self._ip = ip
        self._port = port
        self._device_id = device_id
        self._timeout = float(timeout or 5.0)
        self._local_ip = local_ip
        self._local_port = local_port
        self._req_id = 0  # for request-id matching

    def _next_id(self) -> int:
        self._req_id = (self._req_id + 1) & 0x7FFFFFFF
        if self._req_id == 0:
            self._req_id = 1
        return self._req_id

    async def _udp_call(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send a single UDP request and wait for one JSON response using asyncio.
        Returns the parsed JSON dict or None on timeout or error.
        """
        loop = asyncio.get_running_loop()

        # Ensure a fresh request id and work on a copy
        payload = dict(payload or {})
        req_id = self._next_id()
        payload["id"] = req_id

        data = json.dumps(payload).encode("utf-8")

        # Debug log the outgoing request
        try:
            local_info = ""
            if self._local_ip or self._local_port:
                local_info = f" (local: {self._local_ip or 'auto'}:{self._local_port or 'auto'})"
            _LOGGER.debug("UDP request -> %s:%s%s | %s", self._ip, self._port, local_info, json.dumps(payload))
        except Exception:
            local_info = ""
            if self._local_ip or self._local_port:
                local_info = f" (local: {self._local_ip or 'auto'}:{self._local_port or 'auto'})"
            _LOGGER.debug("UDP request -> %s:%s%s | (non-serializable payload)", self._ip, self._port, local_info)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Keep SO_REUSEADDR; REMOVE SO_REUSEPORT
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            if self._local_port:
                try:
                    sock.bind((self._local_ip or "0.0.0.0", int(self._local_port)))
                except Exception as exc:
                    _LOGGER.error(
                        "UDP bind failed on %s:%s - %s",
                        self._local_ip or "0.0.0.0", self._local_port, exc
                    )

            # Connect so the kernel only accepts packets from the right peer
            # # try:
            # #     sock.connect((self._ip, self._port))
            # # except Exception as exc:
            # #     _LOGGER.error("UDP connect failed to %s:%s - %s", self._ip, self._port, exc)
            # #     sock.close()
            # #     return None

            sock.setblocking(False)

            recv_queue: asyncio.Queue[tuple[bytes, tuple]] = asyncio.Queue()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: _UDPClientProtocol(recv_queue),
                sock=sock
            )
            sock = None  # handover to transport

            try:
                # On a connected socket, no addr tuple is needed
                # # transport.sendto(data)
                transport.sendto(data, (self._ip, self._port))

                deadline = loop.time() + self._timeout
                while True:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        _LOGGER.error("UDP timeout waiting for response from %s:%s", self._ip, self._port)
                        return None

                    try:
                        resp_bytes, addr = await asyncio.wait_for(recv_queue.get(), timeout=remaining)
                    except asyncio.TimeoutError:
                        _LOGGER.error("UDP timeout waiting for response from %s:%s", self._ip, self._port)
                        return None

                    text = resp_bytes.decode("utf-8", "ignore")
                    _LOGGER.debug("UDP response <- %s:%s | %s", addr[0], addr[1], text)

                    # Sender IP verification (belt & suspenders; connect() already filters)
                    if addr and addr[0] != self._ip:
                        _LOGGER.debug("Ignoring packet from unexpected sender %s (expect %s)", addr, self._ip)
                        continue

                    try:
                        obj = json.loads(text)
                    except Exception as exc:
                        _LOGGER.debug("Ignoring non-JSON UDP payload: %s", exc)
                        continue

                    if not isinstance(obj, dict):
                        _LOGGER.debug("Ignoring non-dict UDP JSON")
                        continue

                    # Request-id verification
                    if obj.get("id") != req_id:
                        _LOGGER.debug("Ignoring mismatched reply id=%s (expected %s)", obj.get("id"), req_id)
                        continue

                    return obj

            except Exception as exc:
                _LOGGER.error("UDP error to %s:%s - %s", self._ip, self._port, exc)
                return None
            finally:
                transport.close()

        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

        return None


    # region ES (Energy System) Methods
    # The ES (Energy System) component contains the device's basic power information 
    # and energy statistics, and can configure or monitor the device's operating status.

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """ES.GetStatus: Query the device's basic electrical energy information"""
        payload = {"id": 1, "method": "ES.GetStatus", "params": {"id": "0"}}
        resp = await self._udp_call(payload)
        if not resp:
            return None
        result = resp.get("result") if isinstance(resp, dict) else None
        return result if isinstance(result, dict) else resp if isinstance(resp, dict) else None

    async def get_mode(self) -> Optional[Dict[str, Any]]:
        """ES.GetMode: Get information about the operating mode of the device"""
        payload = {"id": 1, "method": "ES.GetMode", "params": {"id": 0}}
        resp = await self._udp_call(payload)
        if not resp:
            return None
        result = resp.get("result") if isinstance(resp, dict) else None
        return result if isinstance(result, dict) else resp if isinstance(resp, dict) else None

    async def set_mode(self, mode: str, **cfg) -> bool:
        """ES.SetMode: Congure the device's operating mode"""
        config = {"mode": mode}
        for k, v in cfg.items():
            if v is not None:
                config[k] = v
        payload = {"id": 1, "method": "ES.SetMode", "params": {"id": 0, "config": config}}
        resp = await self._udp_call(payload)
        if not resp or not isinstance(resp, dict):
            return False
        result = resp.get("result")
        if isinstance(result, dict):
            ok = result.get("set_result")
            return bool(ok) if ok is not None else True
        return False
    
    # endregion ES (Energy System) Methods


    # region Bat (Battery) Methods
    # The Bat (Battery) component contains basic information about the device's battery

    async def get_battery_status(self):
        """Bat.GetStatus: Query the device's battery information and operating status"""
        payload = {"id": 1, "method": "Bat.GetStatus", "params": {"id": 0}}
        resp = await self._udp_call(payload)
        if not resp:
            return None
        result = resp.get("result") if isinstance(resp, dict) else None
        return result if isinstance(result, dict) else resp if isinstance(resp, dict) else None
    
    # endregion Bat (Battery) Methods