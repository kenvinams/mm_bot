from typing import List, Optional

from core.entities import SpotOrder


class BackLog:

    def __init__(self):
        hanging_orders: Optional[List[SpotOrder]] = []

    def insert_order(self, order: SpotOrder):
        pass

    def pop(self, order: SpotOrder):
        pass

    def get_all(self):
        pass
