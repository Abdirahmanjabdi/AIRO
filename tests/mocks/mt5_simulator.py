from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


_initialized = False
_last_error: tuple[int, str] = (0, "success")


@dataclass
class AccountInfo:
    login: int
    server: str
    balance: float = 10_000.0
    equity: float = 10_000.0
    leverage: int = 100


@dataclass
class Deal:
    position_id: int
    time: int
    time_msc: int
    price: float
    volume: float
    profit: float
    swap: float
    commission: float
    fee: float
    symbol: str


@dataclass
class Order:
    sl: float
    tp: float


def _mode() -> str:
    return os.getenv("SENTINEL_MT5_SIMULATOR_MODE", "success").lower()


def initialize(login: int | None = None, server: str | None = None, password: str | None = None) -> bool:
    global _initialized, _last_error
    if _mode() == "fail":
        _initialized = False
        _last_error = (10001, "simulated login failure")
        return False

    if login is None or server is None or password is None:
        _initialized = False
        _last_error = (10002, "missing credentials")
        return False

    _initialized = True
    _last_error = (0, "success")
    return True


def shutdown() -> bool:
    global _initialized
    _initialized = False
    return True


def last_error() -> tuple[int, str]:
    return _last_error


def account_info() -> AccountInfo | None:
    if not _initialized:
        return None
    return AccountInfo(
        login=int(os.getenv("SENTINEL_MT5_SIMULATOR_LOGIN", "98765432")),
        server=os.getenv("SENTINEL_MT5_SIMULATOR_SERVER", "ICMarkets-Demo"),
    )


def history_orders_get(position: int | None = None) -> list[Order]:
    _ = position
    return [Order(sl=1.0950, tp=1.1150)]


def history_deals_get(date_from: datetime, date_to: datetime) -> list[Deal] | None:
    _ = date_from
    _ = date_to

    if not _initialized:
        return None

    mode = _mode()
    if mode == "blank":
        return []
    if mode == "fail":
        return None

    count = int(os.getenv("SENTINEL_MT5_SIMULATOR_TRADE_COUNT", "100"))
    base_time = datetime.now(timezone.utc) - timedelta(days=max(count // 2, 1))

    deals: list[Deal] = []
    for index in range(count):
        position_id = index + 1
        open_time = base_time + timedelta(minutes=index * 30)
        close_time = open_time + timedelta(minutes=15)
        open_price = 1.1000 + (index * 0.0004)
        close_price = open_price + (0.0015 if index % 3 else -0.0008)
        volume = 0.5 + ((index % 4) * 0.25)
        profit = round((close_price - open_price) * 10000 * volume, 2)
        symbol = "EURUSD" if index % 2 == 0 else "GBPUSD"

        deals.append(
            Deal(
                position_id=position_id,
                time=int(open_time.timestamp()),
                time_msc=int(open_time.timestamp() * 1000),
                price=round(open_price, 5),
                volume=volume,
                profit=0.0,
                swap=0.0,
                commission=-0.15,
                fee=0.0,
                symbol=symbol,
            )
        )
        deals.append(
            Deal(
                position_id=position_id,
                time=int(close_time.timestamp()),
                time_msc=int(close_time.timestamp() * 1000),
                price=round(close_price, 5),
                volume=volume,
                profit=profit,
                swap=0.0,
                commission=-0.15,
                fee=0.0,
                symbol=symbol,
            )
        )

    return deals


def main() -> None:
    initialize(
        login=int(os.getenv("SENTINEL_MT5_SIMULATOR_LOGIN", "98765432")),
        server=os.getenv("SENTINEL_MT5_SIMULATOR_SERVER", "ICMarkets-Demo"),
        password=os.getenv("SENTINEL_MT5_SIMULATOR_PASSWORD", "mock-password"),
    )
    deals = history_deals_get(datetime.now(timezone.utc) - timedelta(days=30), datetime.now(timezone.utc))
    print(f"mode={_mode()} initialized={_initialized} deals={0 if deals is None else len(deals)}")
    shutdown()


if __name__ == "__main__":
    main()
