import datetime


class PriceCandles:
    def __init__(
        self,
        timestamp: datetime.datetime.timestamp,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        period: str,
    ):
        """
        Period accepted values: M1, M3, M5, M15, M30, H1, H4, D1, D7, 1M.
        """
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.period = period


class Tickers:
    def __init__(
        self,
        timestamp: datetime.datetime.timestamp,
        open: float,
        high: float,
        low: float,
        close: float,
        ask: float,
        bid: float,
        volume: float,
    ):
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.ask = ask
        self.bid = bid
        self.volume = volume
