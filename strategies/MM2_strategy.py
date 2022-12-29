from typing import List
import time

from core.entities import SpotOrder, OrderBook, PriceCandles, TradeSide, OrderType
from core.exchange import SpotExchange
from strategies import StrategyBase

class StrategyCls(StrategyBase):
    def __init__(self, exchange_bases: List[SpotExchange]):
        super().__init__(exchange_bases)

    def _run(self):
        print(self.exchange_base.inventory.get_current_balances)
        

      
        
        
