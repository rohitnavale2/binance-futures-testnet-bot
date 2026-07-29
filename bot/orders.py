"""
High-level order placement logic.

Sits between the CLI layer (cli.py) and the low-level REST client
(client.py). Responsible for:
    - turning validated CLI input into a Binance order payload
    - logging a clear "order request summary" before sending
    - logging a clear "order response" / success-failure summary after
    - re-raising typed errors from the client layer so the CLI can present
      a clean message
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from .client import BinanceAPIError, BinanceNetworkError, FuturesTestnetClient
from .logging_config import get_logger

logger = get_logger("orders")


@dataclass
class OrderRequest:
    symbol: str
    side: str          # BUY / SELL
    order_type: str     # MARKET / LIMIT / STOP_LIMIT
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: str = "GTC"  # Good-Til-Canceled, applies to LIMIT orders

    def summary(self) -> str:
        parts = [
            f"symbol={self.symbol}",
            f"side={self.side}",
            f"type={self.order_type}",
            f"quantity={self.quantity}",
        ]
        if self.price is not None:
            parts.append(f"price={self.price}")
        if self.stop_price is not None:
            parts.append(f"stopPrice={self.stop_price}")
        if self.order_type in ("LIMIT", "STOP_LIMIT"):
            parts.append(f"timeInForce={self.time_in_force}")
        return " | ".join(parts)


class OrderExecutionError(Exception):
    """Raised when order placement fails for any reason (API or network)."""


def _build_binance_params(req: OrderRequest) -> Dict[str, Any]:
    """Translate our internal OrderRequest into Binance /fapi/v1/order params."""
    params: Dict[str, Any] = {
        "symbol": req.symbol,
        "side": req.side,
        "type": "LIMIT" if req.order_type == "STOP_LIMIT" else req.order_type,
        "quantity": str(req.quantity),
    }

    if req.order_type == "LIMIT":
        params["price"] = str(req.price)
        params["timeInForce"] = req.time_in_force

    elif req.order_type == "STOP_LIMIT":
        # Binance futures models stop-limit as type=STOP with a price + stopPrice.
        params["type"] = "STOP"
        params["price"] = str(req.price)
        params["stopPrice"] = str(req.stop_price)
        params["timeInForce"] = req.time_in_force

    return params


def place_order(client: FuturesTestnetClient, req: OrderRequest) -> Dict[str, Any]:
    """
    Place an order on Binance Futures Testnet and return the parsed response.
    Raises OrderExecutionError on any failure (API error or network error).
    """
    logger.info("Order request summary: %s", req.summary())

    params = _build_binance_params(req)

    try:
        response = client.new_order(**params)
    except BinanceAPIError as exc:
        logger.error("Order FAILED (API error): %s", exc)
        raise OrderExecutionError(str(exc)) from exc
    except BinanceNetworkError as exc:
        logger.error("Order FAILED (network error): %s", exc)
        raise OrderExecutionError(str(exc)) from exc

    order_id = response.get("orderId")
    status = response.get("status")
    executed_qty = response.get("executedQty")
    avg_price = response.get("avgPrice")

    logger.info(
        "Order SUCCEEDED: orderId=%s status=%s executedQty=%s avgPrice=%s",
        order_id, status, executed_qty, avg_price,
    )

    return response
