from typing import List
import time

from core.entities import SpotOrder, OrderBook, PriceCandles, TradeSide, OrderType
from core.exchange import SpotExchange
from strategies import StrategyBase


class StrategyCls(StrategyBase):
    def __init__(self, exchange_bases: List[SpotExchange]):
        super().__init__(exchange_bases)
        self._count = 0
        self.spread = 0.08
        self._last_buy_price = 0
        self._last_sell_price = 0

    def _run(self):
        print(self.exchange_base.inventory.get_all_balances)
        # print(self.exchange_base.pair.current_ticker.close)
        # print(self.exchange_base.pair.current_candles.close)
        # print(self.exchange_base.pair.get_mid_price)
        # print(self.exchange_base.pair.get_reference_price)
        # print(self.exchange_base.pair.current_orderbook.bids)
        # print(self.exchange_base.pair.current_orderbook.asks)
        # print(len(self.exchange_base.pair.orderbooks))
        # print(self.exchange_base.pair.current_orderbook.get_mid_price)
        # print(self.exchange_base.pair.current_orderbook.get_best_bid)
        # print(self.exchange_base.pair.current_orderbook.get_best_ask)
        # print(self.exchange_base.pair.current_orderbook.timestamp)
        # self.exchange_base.create_spot_order(SpotOrder(10000,1.04,TradeSide.BUY, OrderType.LIMIT, self.exchange_base.pair))
        pass

