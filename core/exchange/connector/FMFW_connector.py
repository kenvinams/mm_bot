import aiohttp
import json
from base64 import b64encode
import datetime as dt
from typing import List
from urllib.parse import urlencode

import global_settings
from core.entities import SpotOrder, OrderBook, PriceCandles, Tickers, TradeSide, OrderType, OrderStatus
from core.exchange.connector.base_connector import BaseConnector
from core.utils import setup_custom_logger, time_out


def _build_headers(api_key: str, secret_key: str):
    msg = api_key + ':' + secret_key
    msg = b64encode(msg.encode()).decode()
    headers = {'Authorization': 'Basic ' + msg}
    return headers

def convert_timestamp(ts):
    """
    Convert ISO timestamp from FMFW to unix timestamp.
    """
    unix_timestamp = dt.datetime.fromisoformat(ts[:19]).timestamp()
    return unix_timestamp

class FMFWConnector(BaseConnector):
    def __init__(self):
        super().__init__()
        self._api_endpoint = 'https://api.fmfw.io'
        self._ws_endpoint = 'wss://api.fmfw.io/api/3/ws/public'
        self._ws_trading_endpoint = 'wss://api.fmfw.io/api/3/ws/trading'
        self._ws_wallet_endpoint = 'wss://api.fmfw.io/api/3/ws/wallet'
        self.logger = setup_custom_logger(__name__,log_level=global_settings.LOG_LEVEL)
        self._market_rate_limit = 30
        self._trading_rate_limit = 300
        self._other_rate_limit = 20
        self._ws_available = False

    def _modify_order_model(self,response):
        side = response['side']
        if side == 'buy':
            side = TradeSide.BUY
        else:
            side = TradeSide.SELL
        status = response['status']
        if status == 'new':
            status = OrderStatus.NEW
        elif status == 'partiallyFilled':
            status = OrderStatus.PARTIALLY_FILLED
        elif status == 'filled':
            status = OrderStatus.FILLED
        else:
            status = OrderStatus.CANCELED
        typ = response['type']
        if typ == 'limit':
            typ = OrderType.LIMIT
        else:
            typ = OrderType.MARKET
        created_time = response['created_at']
        created_at = convert_timestamp(created_time)
        updated_time = response['updated_at']
        updated_at = convert_timestamp(updated_time)
        pair = self.get_pair(response['symbol'])
        spot_order = SpotOrder(float(response['quantity']), float(response['price']), side, typ,pair, status,
                            response['client_order_id'], float(response['quantity_cumulative']), created_at, updated_at)
        return spot_order
    
    async def _get_inventory_balance(self):
        """Get inventory balance. Signed method.
        Returns:
            Balance (dict): symbols with balance.
        """
        response = await self._curl('/api/3/spot/balance', auth=True)
        data = {}
        if len(response) > 0:
            for i in response:
                # reserved = float(i['reserved'])
                data[i['currency']] = float(i['available'])
            return data
        else:
            return None

    async def _get_order_book(self, symbols: List[str]):
        """Fetch orderbook by symbol. Public method.
        Args:
            symbols (List): list of token symbols.
        Returns:
            orderbook_dict (dict): dict of token symbol with orderbook.
        """
        response = await self._curl('/api/3/public/orderbook', query={'depth': 0, 'symbols': ','.join(symbols)})
        if len(response) != len(symbols):
            self.logger.error('Total number of symbols larger than input')
            return None
        else:
            orderbooks = {}
            for s in symbols:
                timestamp = response[s]['timestamp']
                unix_timestamp = convert_timestamp(timestamp)
                bid = [[float(x[0]), float(x[1])] for x in response[s]['bid']]
                ask = [[float(x[0]), float(x[1])] for x in response[s]['ask']]
                orderbooks[s] = OrderBook(bid, ask, unix_timestamp)
            return orderbooks

    async def _create_spot_order(self, spot_order: SpotOrder):
        """Create a spot order.
        Args:
            spot_order (SpotOrder): a spot order base model.
                volume (float): volume to quote of the order.
                price (float): price to quote (in quote asset) for the order.
                trade_size (TradeSide): Buy or Sell side.
                order_type (OrderType): Limit or Market order.
                trading_pair (str): Trading pair of the order.
        Returns:
            Spot order.
                client_order_id (str): Order unique identifier as assigned by trader.
                    Uniqueness must be guaranteed within a single trading day, including all active orders.
                symbol (str): Symbol code.
                side (TradeSide): Trade side.
                status (OrderStatus): Order state.
                type (OrderType): Order type.
                quantity (float): Order quantity.
                quantity_cumulative (float): Executed order quantity.
                price (float): Optional. Order price.
                created_at (timestamp): Date of order's creation.
                updated_at (timestamp): Date of order's last update.
        """
        quantity = spot_order.quantity
        quote_price = spot_order.price
        trade_side = spot_order.side
        order_type = spot_order.order_type
        pair = spot_order.pair
        quantity = self._round_nearest(quantity, pair.quantity_increment)
        quote_price = self._round_nearest(quote_price, pair.tick_size)
        order_id = spot_order.order_id  # CREATE CLIENT ORDER ID FOR ORDER MANAGEMENTS
        if trade_side == TradeSide.BUY:
            side = 'buy'
        elif trade_side == TradeSide.SELL:
            side = 'sell'
        else:
            side = None
        if order_type == OrderType.LIMIT:
            typ = 'limit'
        elif order_type == OrderType.MARKET:
            typ = 'market'
        else:
            typ = None
        if order_type == OrderType.LIMIT:
            post_dict = {'client_order_id': order_id, 'symbol': pair.trading_pair,
                        'side': side, 'quantity': quantity, 'price': quote_price, 'type': typ}
        else:
            post_dict = {'client_order_id': order_id, 'symbol': pair.trading_pair,
                        'side': side, 'quantity': quantity, 'type': typ}
        response = await self._curl('/api/3/spot/order', auth=True,verb='POST', post_dict=post_dict)
        if response is not None:
            spot_order.status = OrderStatus.FILLED
            spot_order.quantity_cumulative = spot_order.quantity
        return spot_order

    async def _cancel_spot_order(self, spot_order:SpotOrder):
        """Cancel a spot order.
        Args:
            client_order_id (str): client order id.
        Returns:
            Spot order
        """
        client_order_id = spot_order.order_id
        response = await self._curl('/api/3/spot/order/', auth=True,verb='DELETE', attribute=client_order_id)
        if response is not None:
            spot_order.status = OrderStatus.CANCELED
            spot_order.quantity_cumulative = float(response['quantity_cumulative'])
            spot_order.updated_at = convert_timestamp(response['updated_at'])
            spot_order.created_at = convert_timestamp(response['created_at'])
            return spot_order
        else:
            return None

    async def _cancel_spot_orders(self, spot_orders: List[SpotOrder]):
        data = []
        for spot_order in spot_orders:
            res = await self._cancel_spot_order(spot_order)
            if res is not None:
                data.append(res)
        return data

    async def _cancel_all_spot_orders(self, symbols:List[str]):
        """Cancel all spot orders.
        Returns: 
            Array of spot orders.
        """
        response = await self._curl('/api/3/spot/order', auth=True,verb='DELETE')
        if len(response) < 1:
            return []
        else:
            res = []
            for r in response:
                spot_order = self._modify_order_model(r)
                res.append(spot_order)
        return res

    async def _get_active_spot_orders(self):
        """Get all active spot orders.
        Returns: 
            Array of active spot orders.
        """
        response = await self._curl('/api/3/spot/order', auth=True)
        if response is not None:
            if len(response) < 1:
                return []
            else:
                res = []
                for r in response:
                    spot_order = self._modify_order_model(r)
                    res.append(spot_order)
                return res
        else:
            return []

    async def _get_trading_candles(self, symbols: List[str], period: str = 'M1'):
        """Get candles for a list of symbols.
        Args:
            symbols (List): List of symbols.
            period (str): Period of candles. M1, 1D.
        Returns:
            dict_price_candles (Dict): Dict of PriceCandles.
            PriceCandle.
        """
        query = {'symbols': ','.join(symbols), 'period': period, 'limit': 1}
        response = await self._curl('/api/3/public/candles', query=query)
        if len(response) != len(symbols):
            return None
        else:
            price_candles = {}
            for s in symbols:
                data = response[s][0]
                timestamp = data['timestamp']
                unix_timestamp = convert_timestamp(timestamp)
                price_candle = PriceCandles(unix_timestamp, float(data['open']),
                                            float(data['max']), float(data['min']), float(data['close']),
                                            float(data['volume']), period)
                price_candles[s] = price_candle
        return price_candles

    async def _get_tickers(self, symbols: List[str]):
        """Get tickers information for a list of symbols.
        Args:
        symbols (List): List of symbols.
        Returns:
            dict_tickers (dict): Dict of Tickers.
            ask (float): Best ask price. Can return null if no data.
            bid (float): Best bid price. Can return null if no data.
            close (float): Last trade price. Can return null if no data.
            low (float): The lowest trade price within 24 hours.
            high (float): The highest trade price within 24 hours.
            open (float): Last trade price 24 hours ago. Can return null if no data.
            volume (float): Total trading amount within 24 hours in base currency.
            timestamp (float): Last update or refresh ticker timestamp.
        """
        query = {'symbols': ','.join(symbols)}
        response = await self._curl('/api/3/public/ticker', query=query)
        if len(response) != len(symbols):
            return None
        else:
            tickers = {}
            for s in symbols:
                timestamp = response[s]['timestamp']
                unix_time = convert_timestamp(timestamp)
                ticker = Tickers(unix_time, float(response[s]['open']), float(response[s]['high']), 
                                float(response[s]['low']),float(response[s]['last']), float(response[s]['ask']), 
                                float(response[s]['bid']),float(response[s]['volume']))
                tickers[s] = ticker
            return tickers

    async def _get_commission(self, symbols: List[str]) -> dict:
        """Get taker and maker rate for symbols.
        Args:
            symbols (List[str]): List of symbols available on FMFW.
        Returns:
            dict: dict of symbols, values are tuple of take_rate and make_rate
        """
        temp = []
        for i in symbols:
            response = await self._curl('/api/3/spot/fee/', auth=True,attribute=i)
            temp.append(response)
        if all(temp):
            return {symbols[i]: tuple([temp[i]['take_rate'], temp[i]['make_rate']]) for i in range(len(temp))}
        else:
            # READ DATA FROM CONFIG
            pass
    
    @time_out
    async def _curl(self, path: str, auth:bool=False, verb: str = None,
                    query: dict = None, post_dict: dict = None, attribute: str = None, retry_count: int = 0):
        """Send a request to Server."""
        if not verb:
            verb = 'GET'
        if auth:
            headers = _build_headers(self._api_key, self._secret_key)
        else:
            headers = {}
        max_retries = self._retries  # set max retry number
        # create URL FMFW
        url = self._api_endpoint + path
        if attribute:
            url += attribute
        if query:
            url += '?' + urlencode(query)
        response = None

        async def retry():
            r = await self._curl(path, auth, verb, query, post_dict, attribute, retry_count + 1)
            return r

        try:
            # logger needed here.
            if verb == 'GET':
                async with self._session.get(url, headers=headers) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
            elif verb == 'POST':
                async with self._session.post(url, headers=headers, data=post_dict) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
            elif verb == 'PATCH':
                async with self._session.patch(url, headers=headers, data=post_dict) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
            elif verb == 'PUT':
                async with self._session.put(url, headers=headers, data=post_dict) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
            elif verb == 'DELETE':
                async with self._session.delete(url, headers=headers, data=post_dict) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
        
        except aiohttp.ClientResponseError as e:
            """
            HTTP Status Codes ::
            200 OK. Successful request
            400 Bad Request. Returns JSON with the error message
            401 Unauthorized. Authorization is required or has been failed
            403 Forbidden. Action is forbidden
            404 Not Found. Data requested cannot be found
            429 Too Many Requests. Your connection has been rate limited
            500 Internal Server. Internal Server Error
            503 Service Unavailable. Service is down for maintenance
            504 Gateway Timeout. Request timeout expired
            """
            resp_status = resp.status
            if response is None:
                raise e

            # 400 Bad Request. Returns JSON with the error message
            if resp_status == 400:
                self.logger.error('Bad Request.')
                if retry_count < max_retries:
                    return await retry()
                else:
                    return None

            # 401 Unauthorized. Authorization is required or has been failed
            elif resp_status == 401:
                self.logger.error("API Key or Secret incorrect, please check and restart.")
                raise e

            # 403 Forbidden. Action is forbidden
            elif resp_status == 403:
                self.logger.error("Forbidden. Please restart.")
                raise e

            # 404 Not Found. Data requested cannot be found
            elif resp_status == 404:
                self.logger.error("Unable to contact the   API (404).")
                if retry_count < max_retries:
                    return await retry()
                else:
                    return None

            # 429 Too Many Requests. Your connection has been rate limited
            elif resp_status == 429:
                self.logger.error("Ratelimited on current request. Sleeping, then trying again.")
                if retry_count < max_retries:
                    return await retry()
                else:
                    return None

            # 500 Internal Server. Internal Server Error
            elif resp_status == 500:
                self.logger.error("Internal Server Error")
                raise e

            # 503 Service Unavailable. Service is down for maintenance
            elif resp_status == 503:
                self.logger.warning("Unable to contact the API (503), retrying. ")
                if retry_count < max_retries:
                    return await retry()
                else:
                    return None

            # 504 Gateway Timeout. Request timeout expired
            elif resp_status == 504:
                self.logger.error("Request timeout expired")
                if retry_count < max_retries:
                    return await retry()
                else:
                    return None
            else:
                raise e
        
        except Exception as e:
            raise e
        if query:
            self.logger.info(f'Successful {verb} request with query {query}')
        else:
            self.logger.info(f'Successful {verb} request with post_dict {post_dict}')
        return json.loads(response)
