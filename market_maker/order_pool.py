from typing import List

from core.entities import SpotOrder
from core.exchange import SpotExchange, OrderManager


class OrderPool:
    def __init__(self, exchange_bases: List[SpotExchange]) -> None:
        self._exchange_bases = exchange_bases
        self._orders = {}

    def get_all_orders(self):
        return self._orders

    def insert_order(self, order: SpotOrder, exchange: SpotExchange):
        pass 

    def _register_exchange(self):
        self._orders = {exchange_base.exchange_name: exchange_base._orders for exchange_base in self._exchange_bases}

