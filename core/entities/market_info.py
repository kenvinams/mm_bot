from typing import List

from core.entities.pair import Pair
from core.entities.account import Account

class MarketInfo:

    def __init__(self, exchange_name: str, pairs: List[Pair], account: Account):
        self.exchange = exchange_name.upper()
        self.pairs = pairs
        self.account = account

    def add_pair(self, pair: Pair):
        self.pairs.append(pair)
