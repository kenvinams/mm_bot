from typing import List
import time
import numpy as np
import pandas as pd

from core.entities import SpotOrder, OrderBook, PriceCandles,TradeSide, OrderType
from core.exchange import SpotExchange
from strategies import StrategyBase


# def _candles_to_df(candles: List[PriceCandles]):
#     data = [candle.__dict__ for candle in candles]
#     df = pd.DataFrame(data)
#     float_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
#     for c in float_cols:
#         df[c] = pd.to_numeric(df[c], errors='coerce')
#     return df


# def _search_first_greater(element, orders, greater):
#     clone_orders = orders.copy()
#     clone_orders.append((np.inf, 0))
#     clone_orders.insert(0, (-np.inf, 0))

#     left = 0
#     right = clone_orders.__len__()
#     mid = (left + right) // 2

#     while left < right:
#         mid = (left + right) // 2
#         if greater(clone_orders[mid], element) == 1:
#             right = mid - 1
#         elif greater(clone_orders[mid], element) == -1:
#             left = mid + 1
#         else:
#             return mid - 1

#     if left == right:
#         if left == clone_orders.__len__() - 1:
#             return orders.__len__()
#         elif left == 0:
#             return 0
#         else:
#             if greater(clone_orders[left], element) >= 0:
#                 return left - 1
#             else:
#                 return left
#     else:
#         return mid - 1


# def calculate_quote_volume(order_book: OrderBook,
#                            p_threshold):
#     def _greater(x, y):
#         if x[0] > y[0]:
#             return 1
#         elif x[0] < y[0]:
#             return -1
#         else:
#             return 0

#     def _less_than(x, y):
#         return _greater(y, x)

#     mid_price = order_book.get_mid_price()
#     up_ask = mid_price * (1 + p_threshold)
#     down_bid = mid_price * (1 - p_threshold)
#     up_ask_index = _search_first_greater(element=(up_ask, None), orders=order_book.asks, greater=_greater)
#     down_bid_index = _search_first_greater(element=(down_bid, None), orders=order_book.bids, greater=_less_than)
#     asks = order_book.asks[:up_ask_index]
#     bids = order_book.bids[:down_bid_index]
#     ask_vol = np.sum([ask[1] for ask in asks])
#     bid_vol = np.sum([bid[1] for bid in bids])
#     return ask_vol, bid_vol


class StrategyCls(StrategyBase):
    def __init__(self, exchange_bases: List[SpotExchange]):
        super().__init__(exchange_bases)

    def run_strategy(self):
    
        pair = self.exchange_base.pair
        # Cancel all orders
        current_order_book = self.exchange_base.pair.current_orderbook
        delta_bar = 0.08
        mid_price = current_order_book.get_mid_price()
        ask_price = round(mid_price * (1 + delta_bar / 2), 6)
        bid_price = round(mid_price * (1 - delta_bar / 2), 6)
        n_level = 1
        level_offset = 0.01
        ask_orders = []
        bid_orders = []
        for i in range(n_level):
            ask_level_price = ask_price * (1 + i * level_offset)
            ask_orders.append(SpotOrder(1, ask_level_price, TradeSide.SELL, OrderType.LIMIT, pair))
            
            bid_level_price = bid_price * (1 - i * level_offset)
            bid_orders.append(SpotOrder(1, bid_level_price, TradeSide.BUY, OrderType.LIMIT, pair))
            
        all_orders = ask_orders
        all_orders.extend(bid_orders)
        self.exchange_base.create_spot_orders(all_orders)
