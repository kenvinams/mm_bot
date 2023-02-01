from typing import List, Tuple

from core.entities.order_book import OrderBook
from core.entities.price_state import PriceCandles, Tickers
from core.entities.token import Token
import mm_bot.global_settings as global_settings


class Pair:
    def __init__(self, base: Token, quote: Token, symbol: str = None):
        self._base_asset = base
        self._quote_asset = quote
        if not symbol:
            self._trading_pair = base.symbol + quote.symbol
        else:
            self._trading_pair = symbol
        self._max_length = global_settings.DATA_MAX_LENGTH

        self._orderbook: OrderBook = None
        self._trading_candle: PriceCandles = None
        self._ticker: Tickers = None
        self._orderbooks: List[OrderBook] = []
        self._trading_candles: List[PriceCandles] = []
        self._tickers: List[Tickers] = []
        self._taker_rate = None
        self._maker_rate = None
        self._tick_size = None
        self._quantity_increment = None

    @property
    def base_asset(self):
        return self._base_asset.symbol

    @property
    def quote_asset(self):
        return self._quote_asset.symbol

    @property
    def trading_pair(self):
        return self._trading_pair

    @property
    def taker_rate(self):
        return self._taker_rate

    @property
    def maker_rate(self):
        return self._maker_rate

    @property
    def tick_size(self):
        return self._tick_size

    @tick_size.setter
    def tick_size(self, val):
        self._tick_size = val

    @property
    def quantity_increment(self):
        return self._quantity_increment

    @quantity_increment.setter
    def quantity_increment(self, val):
        self._quantity_increment = val

    @property
    def current_orderbook(self):
        return self._orderbook

    @property
    def current_candles(self):
        return self._trading_candle

    @property
    def current_ticker(self):
        return self._ticker

    @property
    def orderbooks(self):
        return self._orderbooks

    @property
    def trading_candles(self):
        return self._trading_candles

    @property
    def tickers(self):
        return self._tickers

    @property
    def get_mid_price(self):
        if self._ticker is not None:
            best_bid = self._ticker.bid
            best_ask = self._ticker.ask
            return (best_ask + best_bid) / 2
        else:
            return None

    @property
    def get_reference_price(self):
        if self._ticker is not None:
            return self._ticker.close
        else:
            return None

    def _set_rate(self, rates: Tuple):
        self._taker_rate, self._maker_rate = rates

    def _add_orderbook(self, orderbook: OrderBook):
        if orderbook is not None:
            self._orderbook = orderbook
            if len(self._orderbooks) < self._max_length:
                self._orderbooks.append(orderbook)
            else:
                self._orderbooks = self._orderbooks[1:] + [orderbook]

    def _add_trading_candles(self, price_candles: PriceCandles):
        if price_candles is not None:
            self._trading_candle = price_candles
            if len(self._trading_candles) < self._max_length:
                self._trading_candles.append(price_candles)
            else:
                self._trading_candles = self._trading_candles[1:] + [price_candles]

    def _add_tickers(self, ticker: Tickers):
        if ticker is not None:
            self._ticker = ticker
            if len(self._tickers) < self._max_length:
                self._tickers.append(ticker)
            else:
                self._tickers = self._tickers[1:] + [ticker]
