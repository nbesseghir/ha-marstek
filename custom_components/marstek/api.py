import json
import socket
import logging
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

class MarstekApiClient:
    def __init__(self, ip: str, port: int, device_id: str, timeout: float = 5.0,
                 local_ip: str | None = None, local_port: int | None = None) -> None:
        self._ip = ip
        self._port = port
        self._device_id = device_id
        self._timeout = float(timeout or 5.0)
        self._local_ip = local_ip
        self._local_port = local_port

    def _udp_call(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = json.dumps(payload).encode("utf-8")
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
                    _LOGGER.error("UDP bind failed on %s:%s - %s", self._local_ip or "0.0.0.0", self._local_port, exc)
            sock.settimeout(self._timeout)
            sock.sendto(data, (self._ip, self._port))
            last_exc = None
            for _ in range(3):
                try:
                    resp, _ = sock.recvfrom(65535)
                    text = resp.decode("utf-8", "ignore")
                    return json.loads(text)
                except Exception as e:
                    last_exc = e
                    continue
            if last_exc:
                raise last_exc
        except Exception as exc:
            _LOGGER.error("UDP error to %s:%s - %s", self._ip, self._port, exc)
            return None
        finally:
            sock.close()

    def get_status(self) -> Optional[Dict[str, Any]]:
        payload = {"id": 1, "method": "ES.GetStatus", "params": {"id": self._device_id}}
        resp = self._udp_call(payload)
        if not resp:
            return None
        if isinstance(resp, dict) and "result" in resp and isinstance(resp["result"], dict):
            return resp["result"]
        return resp if isinstance(resp, dict) else None

    def get_mode(self) -> Optional[Dict[str, Any]]:
        payload = {"id": 1, "method": "ES.GetMode", "params": {"id": 0}}
        resp = self._udp_call(payload)
        if not resp:
            return None
        if isinstance(resp, dict) and "result" in resp and isinstance(resp["result"], dict):
            return resp["result"]
        return resp if isinstance(resp, dict) else None

    def set_mode(self, mode: str, **cfg) -> bool:
        config = {"mode": mode}
        for k, v in cfg.items():
            if v is not None:
                config[k] = v
        payload = {"id": 1, "method": "ES.SetMode", "params": {"id": 0, "config": config}}
        resp = self._udp_call(payload)
        if not resp:
            return False
        if isinstance(resp, dict):
            if resp.get("result") and isinstance(resp["result"], dict):
                r = resp["result"]
                ok = r.get("set_result")
                return bool(ok) if ok is not None else True
        return False

    def get_battery_status(self):
        payload = {"id": 1, "method": "Bat.GetStatus", "params": {"id": 0}}
        resp = self._udp_call(payload)
        if not resp:
            return None
        if isinstance(resp, dict) and "result" in resp and isinstance(resp["result"], dict):
            return resp["result"]
        return resp if isinstance(resp, dict) else None
