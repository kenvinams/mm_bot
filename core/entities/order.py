import datetime
from enum import Enum
from core.entities.pair import Pair

class OrderType(Enum):
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'

class OrderStatus(Enum):
    NEW = 'NEW'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'
    CANCELED = 'CANCELLED'

class TradeSide(Enum):
    BUY = 'BUY'
    SELL = 'SELL'

class SpotOrder:

    def __init__(self, quantity: float,
                 price: float,
                 side: TradeSide,
                 order_type: OrderType,
                 pair: Pair,
                 status: OrderStatus = None,
                 order_id: str = None,
                 quantity_cummulative: float = 0,
                 created_at: datetime.datetime.timestamp = None,
                 updated_at: datetime.datetime.timestamp = None):
        self.order_id = order_id
        self.pair = pair
        self.quantity = quantity
        self.quantity_cumulative = quantity_cummulative
        self.price = price
        self.side = side
        self.order_type = order_type
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
    
    def __str__(self) -> str:
        return f'{self.order_type.value} {self.status.value} Order of pair {self.pair.trading_pair} ' \
        f'with quantity {self.quantity:.3f} and price {self.price:.3f}, filled {self.quantity_cumulative}.'

    def __repr__(self) -> str:
        return f'{self.order_type.value} {self.status.value} Order of pair {self.pair.trading_pair} ' \
        f'with quantity {self.quantity:.3f} and price {self.price:.3f}, filled {self.quantity_cumulative}.'