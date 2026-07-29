"""
Low-level authenticated REST client for Binance Futures Testnet (USDT-M).

This talks directly to the REST API using `requests` (no python-binance
dependency required) so behaviour is fully transparent and easy to audit.
Every request and response is logged via bot.logging_config.

API docs: https://developers.binance.com/docs/derivatives/usds-margined-futures
Testnet base URL: https://testnet.binancefuture.com
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from .logging_config import get_logger

logger = get_logger("client")

DEFAULT_BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW_MS = 5000
REQUEST_TIMEOUT_S = 10


class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx / error-coded response."""

    def __init__(self, message: str, status_code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class BinanceNetworkError(Exception):
    """Raised on connection failures, timeouts, or DNS errors."""


class FuturesTestnetClient:
    """
    Thin wrapper around the Binance USDT-M Futures REST API (testnet).

    Handles:
        - request signing (HMAC-SHA256)
        - timestamp / recvWindow handling
        - structured logging of every request and response
        - translating transport/API errors into typed exceptions
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        session: Optional[requests.Session] = None,
    ):
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret are required.")

        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _sign(self, params: Dict[str, Any]) -> str:
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return signature

    def _signed_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = RECV_WINDOW_MS
        params["signature"] = self._sign(params)

        url = f"{self.base_url}{path}"
        # Redact the signature/key before logging.
        safe_params = {k: v for k, v in params.items() if k != "signature"}
        logger.debug("REQUEST %s %s params=%s", method, url, safe_params)

        try:
            response = self.session.request(
                method, url, params=params, timeout=REQUEST_TIMEOUT_S
            )
        except requests.exceptions.Timeout as exc:
            logger.error("Network timeout calling %s %s: %s", method, url, exc)
            raise BinanceNetworkError(f"Request to {path} timed out after {REQUEST_TIMEOUT_S}s") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network/connection error calling %s %s: %s", method, url, exc)
            raise BinanceNetworkError(f"Could not connect to {self.base_url}: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Unexpected network error calling %s %s: %s", method, url, exc)
            raise BinanceNetworkError(str(exc)) from exc

        logger.debug("RESPONSE status=%s body=%s", response.status_code, response.text)

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        if not response.ok:
            code = body.get("code") if isinstance(body, dict) else None
            msg = body.get("msg") if isinstance(body, dict) else str(body)
            logger.error(
                "API error on %s %s -> HTTP %s code=%s msg=%s",
                method, path, response.status_code, code, msg,
            )
            raise BinanceAPIError(
                f"Binance API error (HTTP {response.status_code}, code={code}): {msg}",
                status_code=response.status_code,
                payload=body,
            )

        return body

    # ------------------------------------------------------------------ #
    # Public endpoints used by the bot
    # ------------------------------------------------------------------ #

    def ping(self) -> Dict[str, Any]:
        """Unsigned connectivity check."""
        url = f"{self.base_url}/fapi/v1/ping"
        logger.debug("REQUEST GET %s", url)
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT_S)
        except requests.exceptions.RequestException as exc:
            logger.error("Ping failed: %s", exc)
            raise BinanceNetworkError(f"Ping failed: {exc}") from exc
        logger.debug("RESPONSE status=%s body=%s", response.status_code, response.text)
        return {"status_code": response.status_code}

    def get_account(self) -> Dict[str, Any]:
        return self._signed_request("GET", "/fapi/v2/account")

    def get_symbol_price(self, symbol: str) -> Dict[str, Any]:
        url = f"{self.base_url}/fapi/v1/ticker/price"
        params = {"symbol": symbol}
        logger.debug("REQUEST GET %s params=%s", url, params)
        try:
            response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
        except requests.exceptions.RequestException as exc:
            logger.error("Price lookup failed for %s: %s", symbol, exc)
            raise BinanceNetworkError(f"Price lookup failed: {exc}") from exc
        logger.debug("RESPONSE status=%s body=%s", response.status_code, response.text)
        return response.json()

    def new_order(self, **params: Any) -> Dict[str, Any]:
        """
        Place a new order. Accepts any valid Binance /fapi/v1/order params,
        e.g. symbol, side, type, quantity, price, timeInForce, stopPrice.
        None-valued params are stripped before sending.
        """
        clean_params = {k: v for k, v in params.items() if v is not None}
        return self._signed_request("POST", "/fapi/v1/order", clean_params)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        return self._signed_request("GET", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id})

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        return self._signed_request("DELETE", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id})
