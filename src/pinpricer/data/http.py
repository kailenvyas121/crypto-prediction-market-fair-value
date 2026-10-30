"""Thread-safe, rate-limited HTTP client with retry and backoff."""

from __future__ import annotations

import threading
import time

import certifi
import requests
from requests.adapters import HTTPAdapter

RETRY_STATUS = {429, 500, 502, 503, 504}


class RateLimiter:
    """Token bucket shared across threads: at most `rate` acquisitions per second."""

    def __init__(self, rate: float, burst: float | None = None):
        self.rate = float(rate)
        self.capacity = float(burst if burst is not None else max(1.0, rate))
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self.rate
            time.sleep(wait)


class HttpClient:
    """GET JSON (or bytes) with a shared rate limit, retries on 429/5xx, and exponential backoff."""

    def __init__(self, base_url: str = "", rate: float = 5.0, max_retries: int = 6, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.limiter = RateLimiter(rate)
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = certifi.where()
        self.session.headers["User-Agent"] = "pinpricer/0.1 (research)"
        adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16)
        self.session.mount("https://", adapter)

    def _request(self, path: str, params: dict | None, headers: dict | None = None) -> requests.Response:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        for attempt in range(self.max_retries + 1):
            self.limiter.acquire()
            try:
                r = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == self.max_retries:
                    raise
            else:
                if r.status_code not in RETRY_STATUS:
                    return r
                if attempt == self.max_retries:
                    r.raise_for_status()
            time.sleep(min(60.0, 0.5 * 2**attempt))
        raise RuntimeError("unreachable")

    def get_json(self, path: str, params: dict | None = None, *, headers: dict | None = None,
                 allow_404: bool = False) -> dict | None:
        r = self._request(path, params, headers)
        if allow_404 and r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def get_bytes(self, url: str, *, allow_404: bool = False) -> bytes | None:
        r = self._request(url, None)
        if allow_404 and r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content
