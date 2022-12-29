import aiohttp
import datetime as dt
import hmac
import hashlib
from typing import List
from urllib.parse import urlencode
import json

import global_settings
from core.entities import SpotOrder, OrderBook, PriceCandles, Tickers, OrderStatus, OrderType, TradeSide
from core.exchange.connector.base_connector import BaseConnector
from core.utils import setup_custom_logger, time_out


class MEXCConnector(BaseConnector):

    def __init__(self):
        super().__init__()
        self.logger = setup_custom_logger(__name__,log_level=global_settings.LOG_LEVEL)
        self._api_endpoint = 'https://www.mexc.com'
        self._order_ids = {}
        self._active_orders = []
        self._ws_available = False
    

    @time_out
    async def _curl(self, path: str, auth: bool = False, verb: str = None, query: dict = None, post_dict: dict = None, attribute: str = None, retry_count: int = 0):
        return await super()._curl(path, auth, verb, query, post_dict, attribute, retry_count)