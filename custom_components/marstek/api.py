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

    async def _udp_call(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send a single UDP request and wait for one JSON response using asyncio.
        Returns the parsed JSON dict or None on timeout or error.
        """
        loop = asyncio.get_running_loop()
        data = json.dumps(payload).encode("utf-8")

        # Debug log the outgoing request
        try:
            _LOGGER.debug("UDP request -> %s:%s | %s", self._ip, self._port, json.dumps(payload))
        except Exception:
            _LOGGER.debug("UDP request -> %s:%s | (non-serializable payload)", self._ip, self._port)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_REUSEPORT", 15), 1)
            except Exception:
                pass

            if self._local_port:
                try:
                    sock.bind((self._local_ip or "0.0.0.0", int(self._local_port)))
                except Exception as exc:
                    _LOGGER.error(
                        "UDP bind failed on %s:%s - %s",
                        self._local_ip or "0.0.0.0", self._local_port, exc
                    )

            sock.setblocking(False)

            recv_queue: asyncio.Queue[tuple[bytes, tuple]] = asyncio.Queue()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: _UDPClientProtocol(recv_queue),
                sock=sock
            )
            sock = None  # handover to transport

            try:
                transport.sendto(data, (self._ip, self._port))

                # Wait for a single response
                resp_bytes, addr = await asyncio.wait_for(
                    recv_queue.get(), timeout=self._timeout
                )
                text = resp_bytes.decode("utf-8", "ignore")

                # Debug log the incoming response
                _LOGGER.debug("UDP response <- %s:%s | %s", addr[0], addr[1], text)

                obj = json.loads(text)
                return obj if isinstance(obj, dict) else None

            except asyncio.TimeoutError:
                _LOGGER.error("UDP timeout waiting for response from %s:%s", self._ip, self._port)
                return None
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

    async def get_status(self) -> Optional[Dict[str, Any]]:
        payload = {"id": 1, "method": "ES.GetStatus", "params": {"id": self._device_id}}
        resp = await self._udp_call(payload)
        if not resp:
            return None
        result = resp.get("result") if isinstance(resp, dict) else None
        return result if isinstance(result, dict) else resp if isinstance(resp, dict) else None

    async def get_mode(self) -> Optional[Dict[str, Any]]:
        payload = {"id": 1, "method": "ES.GetMode", "params": {"id": 0}}
        resp = await self._udp_call(payload)
        if not resp:
            return None
        result = resp.get("result") if isinstance(resp, dict) else None
        return result if isinstance(result, dict) else resp if isinstance(resp, dict) else None

    async def set_mode(self, mode: str, **cfg) -> bool:
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

    async def get_battery_status(self):
        payload = {"id": 1, "method": "Bat.GetStatus", "params": {"id": 0}}
        resp = await self._udp_call(payload)
        if not resp:
            return None
        result = resp.get("result") if isinstance(resp, dict) else None
        return result if isinstance(result, dict) else resp if isinstance(resp, dict) else None
