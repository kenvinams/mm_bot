from abc import ABC, abstractmethod
from decimal import Decimal
import importlib
from typing import Tuple, List

import global_settings
from core.entities import OrderBook, SpotOrder, Account
from core.utils import setup_custom_logger

class MarketInfo:
    def __init__(self, exchange: str, trading_pair: str, base_asset: str, quote_asset: str):
        self.EXCHANGE: str = exchange.upper()  # BITRUE, FMFW, BINANCE
        self.TRADING_PAIR: str = trading_pair.upper()
        self.BASE_ASSET: str = base_asset.upper()
        self.QUOTE_ASSET: str = quote_asset.upper()


class BaseConnector(ABC):
    def __init__(self):
        # SETUP MARKET INFO: EXCHANGE, PAIR, MARKET TYPE
        self._market_info = None
        self._exchange_name: str = None
        self._symbol: str = None
        self._base_asset: str = None
        self._quote_asset: str = None

        # SETUP SYSTEM PARAMETERS
        self._retries: int = global_settings.RETRY_NUM
        self._time_out: int = global_settings.TIME_OUT

        # EXCHANGE PARAMETERS
        # Some of this parameters won't be necessary in some cases
        self._rate_limit: int = None  # Rate limit per second
        self._order_limit: int = None  # Trading requests limit per second, all other requests = 20
        self._weight_limit: int = None
        self._tick_size: Decimal = None
        self._quote_precision: int = None
        self._quantity_increment: Decimal = None
        self._receive_window: int = None
        self._order_type: Tuple = None
        self._ws_endpoint: str = None
        self._api_endpoint: str = None

        # ACCOUNT INFORMATION
        self._api_key = None
        self._secret_key = None

        # ATTRIBUTES
        self._session = None
        self._ws_available: bool = False
        self.logger = setup_custom_logger(__name__, log_level=global_settings.LOG_LEVEL)
        self._orders_manager: dict = {}
        self._inventory_balance: dict = None
        self._pairs = []
        self._trading_pairs = []
        self._tokens = []

    @property
    def trading_pairs(self):
        return self._trading_pairs
    
    @property
    def pairs(self):
        return self._pairs
    
    @property
    def tokens(self):
        return self._tokens

    @classmethod
    def _initialize_connector(cls, exchange: str):
        cls_name = cls.__name__
        if cls_name != 'BaseConnector':
            return
        else:
            try:
                module = importlib.import_module(f'core.exchange.connector.{exchange.upper()}_connector')
                connector = getattr(module, f'{exchange.upper()}Connector')
            except (ImportError, AttributeError):
                raise ValueError(f'No connector for exchange {exchange.upper()} existed.')
            return connector

    def register_account(self, account: Account):
        self._api_key, self._secret_key = account.get_login_info()

    async def get_inventory_balance(self):
        res = await self._get_inventory_balance()
        if res is None or len(res) < 1:
            self.logger.warning(f'Fail to fetch inventory balance data of symbols {",".join(self.trading_pairs)}')
            return None
        else:
            self.logger.info(f'Successfully fetch inventory data of symbols {",".join(self.trading_pairs)}')
            return res

    async def get_order_book(self):
        res = await self._get_order_book()
        if res is None or len(res) < 1:
            self.logger.warning(f'Fail to fetch orderbook data of symbols {",".join(self.trading_pairs)}')
            return None
        else:
            self.logger.info(f'Successfully fetch orderbook data of symbols {",".join(self.trading_pairs)}')
            return res

    async def get_trading_candles(self, period: str = 'M1'):
        res =  await self._get_trading_candles(period)
        if res is None or len(res) < 1:
            self.logger.warning(f'Fail to fetch candles data of symbols {",".join(self.trading_pairs)}')
            return None
        else:
            self.logger.info(f'Successfully fetch candles data of symbols {",".join(self.trading_pairs)}')
            return res

    async def get_tickers(self):
        res = await self._get_tickers()
        if res is None or len(res) < 1:
            self.logger.warning(f'Fail to fetch ticker data of symbols {",".join(self.trading_pairs)}')
            return None
        else:
            self.logger.info(f'Successfully fetch ticker data of symbols {",".join(self.trading_pairs)}')
            return res

    async def get_active_spot_orders(self):
        res = await self._get_active_spot_orders()
        if res is None or len(res) < 1:
            return []
        else:
            return res

    async def cancel_spot_orders(self, spot_orders:List[SpotOrder]):
        if not spot_orders:
            return []
        else:
            return await self._cancel_spot_orders(spot_orders)

    async def create_spot_order(self, spot_order: SpotOrder):
        return await self._create_spot_order(spot_order)
    
    async def create_spot_orders(self, spot_orders:List[SpotOrder]):
        if not spot_orders:
            return []
        else:
            return await self._create_spot_orders(spot_orders)
    
    async def query_orders(self, spot_orders:List[SpotOrder]):
        pass

    @abstractmethod
    async def _cancel_spot_orders(self, spot_orders:List[SpotOrder]):
        pass

    @abstractmethod
    async def _create_spot_order(self, spot_order: SpotOrder):
        pass
    
    # @abstractmethod
    async def _create_spot_orders(self, spot_orders:List[SpotOrder]):
        pass

    @abstractmethod
    async def _get_inventory_balance(self):
        pass

    @abstractmethod
    async def _get_order_book(self, symbols: List[str]):
        pass

    @abstractmethod
    async def _get_trading_candles(self, symbols: List[str], period: str = 'M1'):
        pass

    @abstractmethod
    async def _get_tickers(self, symbols: List[str]):
        pass

    # @abstractmethod
    async def _query_orders(self, spot_orders:List[SpotOrder]):
        pass

    @abstractmethod
    async def _get_active_spot_orders(self):
        pass

    # @abstractmethod
    async def _cancel_all_spot_orders(self):
        pass

    @abstractmethod
    async def _cancel_spot_order(self, client_order_id: str):
        pass

    def get_pair(self, symbol: str):
        idx = self._trading_pairs.index(symbol)
        return self._pairs[idx]

    def get_margin_posistion(self):
        """
        GET MARGIN POSITION OF ACCOUNT & TRADING PAIR
        """
        pass

    def _round_nearest(self, num, tickSize):
        """
        Round value to the nearest tick.
        """
        tickDec = Decimal(str(tickSize))
        return Decimal(round(num / tickSize, 0)) * tickDec

    @abstractmethod
    async def _curl(self, path: str, auth: bool = False, verb: str = None,
                    query: dict = None, post_dict: dict = None, attribute: str = None, retry_count: int = 0):
        pass
