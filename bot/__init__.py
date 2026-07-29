"""
Simplified Trading Bot package for Binance Futures Testnet (USDT-M).

Modules:
    client.py          - Low-level authenticated REST client for Binance Futures Testnet
    orders.py           - High-level order placement logic (Market / Limit / Stop-Limit)
    validators.py        - CLI input validation
    logging_config.py    - Central logging configuration (console + rotating file log)
"""

__version__ = "1.0.0"
