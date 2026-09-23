# Simplified Trading Bot — Binance Futures Testnet (USDT-M)

A small, structured Python CLI application for placing MARKET, LIMIT, and
(bonus) STOP_LIMIT orders on the Binance USDT-M Futures Testnet, with proper
input validation, structured logging, and error handling

Built with direct REST calls (`requests` + HMAC-SHA256 signing) — no
`python-binance` dependency required, so the request/response flow is fully
transparent and easy to audit

## Project Structure

```
trading_bot/
  bot/
    __init__.py
    client.py          # Low-level authenticated REST client for Binance Futures Testnet
    orders.py           # Order placement logic (builds request, calls client, logs result)
    validators.py        # CLI input validation
    logging_config.py    # Central logging configuration (console + rotating file log)
  logs/
    sample_trading_bot.log   # Example log covering a MARKET order, LIMIT order,
                               # bonus STOP_LIMIT order, and a validation failure
  cli.py               # CLI entry point (argparse)
  README.md
  requirements.txt
```

## Setup

1. **Create a Binance Futures Testnet account** at
   https://testnet.binancefuture.com and log in with a GitHub account.
2. **Generate API credentials**: on the testnet dashboard, click
   "API Key" and generate a key/secret pair. Fund your testnet futures
   wallet using the built-in faucet if needed.
3. **Install dependencies** (Python 3.9+):

   ```bash
   pip install -r requirements.txt
   ```

4. **Set your credentials** as environment variables (recommended, so they
   never appear in shell history or logs):

   ```bash
   export BINANCE_TESTNET_API_KEY="your_api_key"
   export BINANCE_TESTNET_API_SECRET="your_api_secret"
   ```

   On Windows (PowerShell):
   ```powershell
   $env:BINANCE_TESTNET_API_KEY="your_api_key"
   $env:BINANCE_TESTNET_API_SECRET="your_api_secret"
   ```

   Alternatively, pass `--api-key` / `--api-secret` directly on the command
   line (less secure, visible in shell history).

## How to Run

### Market order

```bash
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

### Limit order

```bash
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 65000
```

### Bonus: Stop-Limit order

```bash
python cli.py --symbol BTCUSDT --side SELL --type STOP_LIMIT \
    --quantity 0.01 --price 64000 --stop-price 64500
```

(Binance Futures models a stop-limit order as `type=STOP` with both `price`
and `stopPrice` — the CLI takes care of that translation for you.)

### CLI options

| Flag | Required | Notes |
|---|---|---|
| `--symbol` | yes | e.g. `BTCUSDT` |
| `--side` | yes | `BUY` or `SELL` |
| `--type` | yes | `MARKET`, `LIMIT`, or `STOP_LIMIT` |
| `--quantity` | yes | order quantity |
| `--price` | for LIMIT/STOP_LIMIT | limit price |
| `--stop-price` | for STOP_LIMIT | trigger price |
| `--time-in-force` | no | `GTC` (default), `IOC`, or `FOK` |
| `--api-key` / `--api-secret` | no | overrides env vars |
| `--base-url` | no | defaults to `https://testnet.binancefuture.com` |

### Example output

```
=== Order Request Summary ===
symbol=BTCUSDT | side=BUY | type=MARKET | quantity=0.01
==============================

=== Order Response ===
orderId:      1001
status:       FILLED
executedQty:  0.01
avgPrice:     64123.50
=======================

[SUCCESS] Order placed successfully.
```

## Logging

Every request, response, and error is written to `logs/trading_bot.log`
(created automatically, rotated at 2 MB / 5 backups). The console only shows
concise INFO-level messages (order summary, success/failure) so it stays
readable, while the log file captures full DEBUG-level detail — including
the raw signed request parameters (with the signature itself redacted) and
raw JSON response bodies — for audit purposes.

`logs/sample_trading_bot.log` in this repo is a real captured log from a
test run and includes:
- one successful MARKET order
- one successful LIMIT order
- one successful bonus STOP_LIMIT order
- one rejected request due to input validation (invalid symbol)

## Error Handling

- **Invalid input** (bad symbol, missing price on a LIMIT order, non-numeric
  quantity, etc.) is caught by `bot/validators.py` before any network call
  is made, and reported with a clear message (exit code `2`).
- **API errors** (e.g. insufficient testnet balance, invalid API key,
  rate limits) raise `BinanceAPIError` in `bot/client.py`, are logged with
  the HTTP status/code/message from Binance, and surfaced to the user as
  `[FAILED] Order could not be placed: ...` (exit code `1`).
- **Network failures** (timeouts, DNS/connection errors) raise
  `BinanceNetworkError` and are handled the same way, so the CLI never
  crashes with a raw traceback for expected failure modes.
- Any truly unexpected exception is caught at the top level of `cli.py`,
  logged with a full traceback (`logger.exception`) for debugging, and
  reported to the user with a generic failure message.

## Assumptions

- Symbols are assumed to be USDT-margined perpetuals (e.g. `BTCUSDT`,
  `ETHUSDT`) per the task's "USDT-M" scope; the validator enforces a
  `...USDT` suffix.
- `LIMIT` and `STOP_LIMIT` orders default to `GTC` (Good-Til-Canceled) time
  in force unless `--time-in-force` is specified.
- Quantity/price precision (`stepSize`/`tickSize` per symbol, via the
  exchange info endpoint) is left to Binance's own order validation rather
  than re-implemented client-side; API-rejected precision errors are
  surfaced as `BinanceAPIError` with Binance's own message.
- `recvWindow` is fixed at 5000 ms, which comfortably covers normal network
  latency to the testnet.
- The bonus order type implemented is **Stop-Limit** (`STOP_LIMIT`), mapped
  to Binance Futures' `STOP` order type with both `price` and `stopPrice`.
- `logs/sample_trading_bot.log` was captured against the live request/response
  logging path in this codebase. Because this sandboxed development
  environment has no outbound network access to `testnet.binancefuture.com`,
  that particular sample run was captured against a minimal local HTTP
  server that mirrors Binance's `/fapi/v1/order` response shape, so the
  logging, validation, and error-handling code paths could be exercised
  end-to-end. The code itself talks to the real
  `https://testnet.binancefuture.com` by default (see `DEFAULT_BASE_URL` in
  `bot/client.py`) — running `cli.py` with real testnet credentials (no
  `--base-url` override) will hit the live Binance Futures Testnet.

## Bonus Implemented

- **Third order type**: Stop-Limit (`STOP_LIMIT`), see above.
