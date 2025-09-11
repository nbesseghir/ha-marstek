"""
Marstek Device API Client

This module provides communication with Marstek energy storage devices via UDP.

API Documentation: https://eu.hamedata.com/ems/resource/agreement/MarstekDeviceOpenApi.pdf

The ES (Energy System) component contains the device's basic power information 
and energy statistics, and can configure or monitor the device's operating status.
"""

from __future__ import annotations

import asyncio
import json 
import socket
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime

_LOGGER = logging.getLogger(__name__)
_PORT_LOCKS: dict[int, asyncio.Lock] = {}

# simple per-port locks to avoid concurrent binds/sends on same port
def _port_lock(p: int) -> asyncio.Lock:
    lock = _PORT_LOCKS.get(p)
    if lock is None:
        lock = asyncio.Lock()
        _PORT_LOCKS[p] = lock
    return lock


class _UDPClientProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue

    def datagram_received(self, data: bytes, addr):
        self.queue.put_nowait((data, addr))

    def error_received(self, exc: Exception):
        _LOGGER.debug("UDP protocol error received: %s", exc)


@dataclass
class BatteryStatus:
    """Battery status response from Bat.GetStatus."""
    id: int = 0 # ID of Instance
    soc: Optional[int] = None  # State of charge percentage
    charg_flag: Optional[bool] = None  # Charge flag
    dischrg_flag: Optional[bool] = None  # Discharge flag
    bat_temp: Optional[float] = None  # Battery temperature in Celsius
    bat_voltage: Optional[float] = None  # Battery voltage
    bat_current: Optional[float] = None  # Battery current
    bat_capacity: Optional[int] = None  # Battery capacity in Wh
    rated_capacity: Optional[int] = None  # Rated capacity in Wh
    error_code: Optional[str] = None  # Error Code
    
    @classmethod
    def from_dict(cls, data: dict) -> "BatteryStatus":
        """Create from API response dict."""
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def to_dict(self) -> dict:
        """Convert to dictionary for coordinator."""
        return {k: v for k, v in self.__dict__.items() if v is not None}

@dataclass
class EnergyStatus:
    """Energy status response from ES.GetStatus."""
    id: int = 0 # ID of Instance
    bat_soc: Optional[int] = None # Total battery SOC, [%]
    bat_cap: Optional[int] = None # Total battery capacity, [Wh]
    pv_power: Optional[int] = None # Solar charging power, [W]
    ongrid_power: Optional[int] = None # Grid-tied power, [W]
    offgrid_power: Optional[int] = None # Off-grid power, [W]
    bat_power: Optional[int] = None # Battery power, [W]
    total_pv_energy: Optional[float] = None # Total solar energy generated, [Wh]
    total_grid_output_energy: Optional[float] = None # Total grid output energy, [Wh]
    total_grid_input_energy: Optional[float] = None # Total grid input energy, [Wh]
    total_load_energy: Optional[float] = None # Total load (or o-grid) energy consumed, [Wh]
    
    @classmethod
    def from_dict(cls, data: dict) -> "EnergyStatus":
        """Create from API response dict."""
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def to_dict(self) -> dict:
        """Convert to dictionary for coordinator."""
        return {k: v for k, v in self.__dict__.items() if v is not None}

@dataclass
class OperatingMode:
    """Operating mode response from ES.GetMode."""
    id: int = 0 # ID of Instance
    mode: Optional[str] = "Unknown"  # Auto, AI, Manual, Passive
    ongrid_power: Optional[int] = None
    offgrid_power: Optional[int] = None
    bat_soc: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "OperatingMode":
        """Create from API response dict."""
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def to_dict(self) -> dict:
        """Convert to dictionary for coordinator."""
        result = {"mode": self.mode}
        for cfg_name in ["auto_cfg", "ai_cfg", "manual_cfg", "passive_cfg"]:
            cfg = getattr(self, cfg_name)
            if cfg:
                result[cfg_name] = cfg
        return result

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
        req_id = payload["id"]

        data = json.dumps(payload).encode("utf-8")

        # Choose the local source port:
        # - if self._local_port is provided, use it
        # - otherwise, bind to the device port (your batteries expect src==dst)
        bind_port = int(self._local_port) if self._local_port else int(self._port)
        bind_ip = self._local_ip or "0.0.0.0"

        # Debug log the outgoing request
        try:
            local_info = f" (local: {bind_ip}:{bind_port})"
            _LOGGER.debug("UDP request -> %s:%s%s | %s", self._ip, self._port, local_info, json.dumps(payload))
        except Exception:
            _LOGGER.debug("UDP request -> %s:%s (local: %s:%s) | (non-serializable payload)", self._ip, self._port, bind_ip, bind_port)

        # serialize per local port to avoid concurrent bind/use races
        async with _port_lock(bind_port):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # Keep SO_REUSEADDR; DO NOT use SO_REUSEPORT
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                # Bind the local source port we want (src==dst behavior)
                try:
                    sock.bind((bind_ip, bind_port))
                except Exception as exc:
                    _LOGGER.error("UDP bind failed on %s:%s - %s", bind_ip, bind_port, exc)
                    try:
                        sock.close()
                    finally:
                        return None

                sock.setblocking(False)

                recv_queue: asyncio.Queue[tuple[bytes, tuple]] = asyncio.Queue()
                transport, protocol = await loop.create_datagram_endpoint(
                    lambda: _UDPClientProtocol(recv_queue),
                    sock=sock
                )
                sock = None  # handover to transport

                try:
                    # Unconnected socket: always pass destination tuple
                    transport.sendto(data, (self._ip, int(self._port)))

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

                        # Only check sender IP (port may differ on some firmwares, but yours now matches)
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

    async def get_status(self) -> Optional[EnergyStatus]:
        """ES.GetStatus: Query the device's basic electrical energy information"""

        payload = {
            "id": self._next_id(), 
            "method": "ES.GetStatus", 
            "params": {"id": 0}
        }
        resp = await self._udp_call(payload)
        if not resp:
            return None
        result = resp.get("result") if isinstance(resp, dict) else None
        return EnergyStatus.from_dict(result) if result else None

    async def get_mode(self) -> Optional[OperatingMode]:
        """ES.GetMode: Get information about the operating mode of the device"""

        payload = {
            "id": self._next_id(), 
            "method": "ES.GetMode", 
            "params": {"id": 0}
        }
        resp = await self._udp_call(payload)
        if not resp:
            return None
        result = resp.get("result") if isinstance(resp, dict) else None
        return OperatingMode.from_dict(result) if result else None

    async def set_mode(self, mode: str, **cfg) -> bool:
        """ES.SetMode: Configure the device's operating mode"""

        config = {"mode": mode}
        for k, v in cfg.items():
            if v is not None:
                config[k] = v
        payload = {
            "id": self._next_id(), 
            "method": "ES.SetMode", 
            "params": {"id": 0, "config": config}
        }
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

    async def get_battery_status(self) -> Optional[BatteryStatus]:
        """Bat.GetStatus: Query the device's battery information and operating status"""

        payload = {
            "id": self._next_id(), 
            "method": "Bat.GetStatus", 
            "params": {"id": 0}
        }
        resp = await self._udp_call(payload)
        if not resp:
            return None
        result = resp.get("result") if isinstance(resp, dict) else None
        return BatteryStatus.from_dict(result) if result else None
    
    # endregion Bat (Battery) Methods
