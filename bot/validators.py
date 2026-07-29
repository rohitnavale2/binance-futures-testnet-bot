"""
Input validation for the trading bot CLI.

All validators raise ValidationError (a thin wrapper around ValueError) with a
human-readable message so the CLI layer can catch a single exception type and
print a clean error instead of a traceback.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}

# Basic sanity pattern for USDT-M perpetual symbols e.g. BTCUSDT, ETHUSDT
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,17}USDT$")


class ValidationError(ValueError):
    """Raised when CLI-supplied order parameters fail validation."""


def validate_symbol(symbol: str) -> str:
    if not symbol:
        raise ValidationError("Symbol is required (e.g. BTCUSDT).")
    symbol = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(symbol):
        raise ValidationError(
            f"Invalid symbol format: '{symbol}'. Expected a USDT-M pair like BTCUSDT."
        )
    return symbol


def validate_side(side: str) -> str:
    if not side:
        raise ValidationError("Side is required (BUY or SELL).")
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValidationError(f"Invalid side: '{side}'. Must be one of {sorted(VALID_SIDES)}.")
    return side


def validate_order_type(order_type: str) -> str:
    if not order_type:
        raise ValidationError("Order type is required (MARKET or LIMIT).")
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type: '{order_type}'. Must be one of {sorted(VALID_ORDER_TYPES)}."
        )
    return order_type


def validate_quantity(quantity) -> Decimal:
    try:
        qty = Decimal(str(quantity))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"Quantity must be a number, got '{quantity}'.")
    if qty <= 0:
        raise ValidationError("Quantity must be greater than 0.")
    return qty


def validate_price(price, order_type: str) -> Decimal | None:
    """
    Price is required for LIMIT / STOP_LIMIT orders and forbidden for MARKET orders.
    """
    if order_type == "MARKET":
        if price is not None:
            raise ValidationError("Price must not be supplied for MARKET orders.")
        return None

    if price is None:
        raise ValidationError(f"Price is required for {order_type} orders.")

    try:
        p = Decimal(str(price))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"Price must be a number, got '{price}'.")
    if p <= 0:
        raise ValidationError("Price must be greater than 0.")
    return p


def validate_stop_price(stop_price, order_type: str) -> Decimal | None:
    if order_type != "STOP_LIMIT":
        if stop_price is not None:
            raise ValidationError("Stop price is only applicable to STOP_LIMIT orders.")
        return None

    if stop_price is None:
        raise ValidationError("Stop price is required for STOP_LIMIT orders.")

    try:
        sp = Decimal(str(stop_price))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"Stop price must be a number, got '{stop_price}'.")
    if sp <= 0:
        raise ValidationError("Stop price must be greater than 0.")
    return sp


def validate_order_request(symbol, side, order_type, quantity, price=None, stop_price=None):
    """
    Run all validators together and return a normalized dict.
    Raises ValidationError on the first failure.
    """
    symbol = validate_symbol(symbol)
    side = validate_side(side)
    order_type = validate_order_type(order_type)
    quantity = validate_quantity(quantity)
    price = validate_price(price, order_type)
    stop_price = validate_stop_price(stop_price, order_type)

    return {
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "price": price,
        "stop_price": stop_price,
    }
