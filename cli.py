#!/usr/bin/env python3
"""
CLI entry point for the Simplified Trading Bot (Binance Futures Testnet).

Examples
--------
Market order:
    python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

Limit order:
    python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 65000

Stop-limit order (bonus):
    python cli.py --symbol BTCUSDT --side SELL --type STOP_LIMIT \\
        --quantity 0.01 --price 64000 --stop-price 64500

API credentials are read from the BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_API_SECRET
environment variables (see README.md), or can be passed explicitly with
--api-key / --api-secret.
"""

from __future__ import annotations

import argparse
import os
import sys

from bot.client import BinanceAPIError, BinanceNetworkError, FuturesTestnetClient, DEFAULT_BASE_URL
from bot.logging_config import get_logger
from bot.orders import OrderExecutionError, OrderRequest, place_order
from bot.validators import ValidationError, validate_order_request

logger = get_logger("cli")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading-bot",
        description="Place MARKET / LIMIT (and bonus STOP_LIMIT) orders on Binance Futures Testnet.",
    )
    parser.add_argument("--symbol", required=True, help="Trading pair, e.g. BTCUSDT")
    parser.add_argument("--side", required=True, choices=["BUY", "SELL", "buy", "sell"], help="Order side")
    parser.add_argument(
        "--type", dest="order_type", required=True,
        choices=["MARKET", "LIMIT", "STOP_LIMIT", "market", "limit", "stop_limit"],
        help="Order type",
    )
    parser.add_argument("--quantity", required=True, help="Order quantity, e.g. 0.01")
    parser.add_argument("--price", default=None, help="Limit price (required for LIMIT / STOP_LIMIT)")
    parser.add_argument(
        "--stop-price", dest="stop_price", default=None,
        help="Stop trigger price (required for STOP_LIMIT)",
    )
    parser.add_argument(
        "--time-in-force", dest="time_in_force", default="GTC",
        choices=["GTC", "IOC", "FOK"], help="Time in force for LIMIT orders (default: GTC)",
    )
    parser.add_argument(
        "--api-key", dest="api_key", default=os.environ.get("BINANCE_TESTNET_API_KEY"),
        help="Binance Futures Testnet API key (defaults to BINANCE_TESTNET_API_KEY env var)",
    )
    parser.add_argument(
        "--api-secret", dest="api_secret", default=os.environ.get("BINANCE_TESTNET_API_SECRET"),
        help="Binance Futures Testnet API secret (defaults to BINANCE_TESTNET_API_SECRET env var)",
    )
    parser.add_argument(
        "--base-url", dest="base_url", default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    return parser


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # --- Validate input -------------------------------------------------
    try:
        validated = validate_order_request(
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            stop_price=args.stop_price,
        )
    except ValidationError as exc:
        logger.error("Input validation failed: %s", exc)
        print(f"\n[FAILED] Invalid input: {exc}\n")
        return 2

    req = OrderRequest(
        symbol=validated["symbol"],
        side=validated["side"],
        order_type=validated["order_type"],
        quantity=validated["quantity"],
        price=validated["price"],
        stop_price=validated["stop_price"],
        time_in_force=args.time_in_force,
    )

    print("\n=== Order Request Summary ===")
    print(req.summary())
    print("==============================\n")

    if not args.api_key or not args.api_secret:
        msg = (
            "Missing API credentials. Set BINANCE_TESTNET_API_KEY and "
            "BINANCE_TESTNET_API_SECRET environment variables, or pass "
            "--api-key / --api-secret."
        )
        logger.error(msg)
        print(f"[FAILED] {msg}\n")
        return 2

    # --- Place order ------------------------------------------------------
    client = FuturesTestnetClient(
        api_key=args.api_key, api_secret=args.api_secret, base_url=args.base_url
    )

    try:
        response = place_order(client, req)
    except OrderExecutionError as exc:
        print(f"[FAILED] Order could not be placed: {exc}\n")
        return 1
    except Exception as exc:  # noqa: BLE001 - last line of defense, always logged
        logger.exception("Unexpected error while placing order")
        print(f"[FAILED] Unexpected error: {exc}\n")
        return 1

    print("=== Order Response ===")
    print(f"orderId:      {response.get('orderId')}")
    print(f"status:       {response.get('status')}")
    print(f"executedQty:  {response.get('executedQty')}")
    print(f"avgPrice:     {response.get('avgPrice')}")
    print("=======================")
    print("\n[SUCCESS] Order placed successfully.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
