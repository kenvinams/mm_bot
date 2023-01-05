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

def _create_signature(secret_key: str, query: str):
    signature = hmac.new(bytes(secret_key,'utf-8'),
                msg = bytes(query,'utf-8'),
                digestmod = hashlib.sha256).hexdigest()
    return signature

class BITRUEConnector(BaseConnector):

    def __init__(self):
        super().__init__()
        self.logger = setup_custom_logger(__name__,log_level=global_settings.LOG_LEVEL)
        self._api_endpoint = 'https://openapi.bitrue.com'
        self._order_ids = {}
        self._active_orders = []
        self._ws_available = False

    async def _get_inventory_balance(self):
        response = await self._curl('/api/v1/account', auth=True)
        print(response)
        data = {}
        if len(response['balances']) > 0:
            for d in response['balances']:
                s = d['asset'].upper()
                if s in self.tokens:
                    f = float(d['free'])
                    data[s] = f
            return data
        else:
            return None

    async def _get_order_book(self):
        orderbooks = {}
        symbols = self.trading_pairs
        ts = dt.datetime.now(dt.timezone.utc).timestamp()
        for s in symbols:
            res = await self._curl('/api/v1/depth',query={'symbol':s})
            if res is not None:
                bid = [[float(x[0]), float(x[1])] for x in res['bids']]
                ask = [[float(x[0]), float(x[1])] for x in res['asks']]
                orderbooks[s] = OrderBook(bid, ask, ts)
        return orderbooks
    
    async def _get_tickers(self):
        tickers = {}
        ts = dt.datetime.now(dt.timezone.utc).timestamp()
        symbols = self.trading_pairs
        for s in symbols:
            res = await self._curl('/api/v1/ticker/24hr', query={'symbol':s})
            if res is not None:
                res = res[0]
                tickers[s] = Tickers(ts, float(res['openPrice']), float(res['highPrice']),
                                    float(res['lowPrice']), float(res['lastPrice']), float(res['askPrice']),
                                    float(res['bidPrice']), float(res['volume']))
        return tickers

    async def _get_trading_candles(self, period: str = 'M1'):
        price_candles = {}
        ts = dt.datetime.now(dt.timezone.utc).timestamp()
        symbols = self.trading_pairs
        for s in symbols:
            res = await self._curl('//', query={'symbol':s, 'period':period}, attribute='kline')
            if res is not None:
                d = res['data'][-1]
                price_candles[s] = PriceCandles(ts, float(d['open']), float(d['high']),
                                            float(d['low']), float(d['close']), float(d['vol']), period)
        return price_candles
    
    async def _create_spot_orders(self, spot_orders: List[SpotOrder]):
        data = []
        for spot_order in spot_orders:
            res = await self._create_spot_order(spot_order)
            data.append(res)
        return data

    async def _create_spot_order(self, spot_order:SpotOrder):
        quantity = spot_order.quantity
        quote_price = spot_order.price
        trade_side = spot_order.side
        order_type = spot_order.order_type
        pair = spot_order.pair
        quantity = self._round_nearest(quantity, pair.quantity_increment)
        quote_price = self._round_nearest(quote_price, pair.tick_size)
        order_id = spot_order.order_id
        if trade_side == TradeSide.BUY:
            side = 'BUY'
        elif trade_side == TradeSide.SELL:
            side = 'SELL'
        else:
            side = None
        if order_type == OrderType.LIMIT:
            query = {'symbol':pair.trading_pair, 'side':side,'type': 'LIMIT','quantity':quantity,
                    'price':quote_price, 'newClientOrderId':order_id}
        elif order_type == OrderType.MARKET:
            query = {'symbol':pair.trading_pair, 'side':side,'type': 'MARKET',
                    'quantity':quantity, 'newClientOrderId':order_id}
        response = await self._curl('/api/v1/order', auth=True, verb='POST', query=query)
        if response is not None:
            spot_order.status = OrderStatus.NEW
            spot_order.created_at = response['transactTime']
            spot_order.updated_at = response['transactTime']
            spot_order.order_id = response['clientOrderId']
            self._order_ids[response['clientOrderId']] = response['orderId']
            return spot_order
        else:
            return None

    async def _cancel_spot_order(self, spot_order:SpotOrder):
        client_order_id = spot_order.order_id
        order_id = self._order_ids[client_order_id]
        ts = int(dt.datetime.now().timestamp()*1000)
        spot_order.updated_at = ts
        spot_order.status = OrderStatus.CANCELED
        response = await self._curl('/api/v1/order',auth = True,verb='DELETE', query={'symbol':spot_order.pair.trading_pair,
                                    'origClientOrderId':client_order_id,'orderId':order_id})
        if response is not None:
            return spot_order
        else:
            return None
    
    async def _cancel_spot_orders(self, spot_orders:List[SpotOrder]):
        data = []
        for spot_order in spot_orders:
            res = await self._cancel_spot_order(spot_order)
            data.append(res)
        return data

    async def _get_active_spot_orders(self):
        data = []
        for symbol in self._trading_pairs:
            result = await self._curl('/api/v1/openOrders', auth=True, query={'symbol':symbol})
            if result is not None:
                if len(result) > 0:
                    for r in result:
                        data.append(r)
                else:
                    self._order_ids = {}
                    self._active_orders = []
                    return []
        main_data = []
        self._order_ids = {}
        for order in data:
            if order['type'] == 'LIMIT':
                typ = OrderType.LIMIT
            else:
                typ = OrderType.MARKET

            if order['side'] == 'BUY':
                side = TradeSide.BUY
            else:
                side = TradeSide.SELL
            if order['status'] == 'NEW':
                status = OrderStatus.NEW
            elif order['status'] == 'FILLED':
                status = OrderStatus.FILLED
            elif order['status'] == 'PARTIALLY_FILLED':
                status = OrderStatus.PARTIALLY_FILLED
            else:
                status = OrderStatus.CANCELED
            order_id = order['orderId']
            spot_order = SpotOrder(float(order['origQty']),float(order['price']),side,typ,self.get_pair(order['symbol']),
                                status=status,order_id=order['clientOrderId'],quantity_cummulative=float(order['cummulativeQuoteQty']),
                                created_at=float(order['time']), updated_at=float(order['updateTime']))
            main_data.append(spot_order)
            self._order_ids[order['clientOrderId']]= order_id
            self._active_orders = main_data
        return main_data

    async def _query_order(self, spot_order:SpotOrder):
        client_order_id = spot_order.order_id
        order_id = self._order_ids[client_order_id]
        res = await self._curl('/api/v1/order', auth=True, query={'symbol':spot_order.pair.trading_pair, 'orderId':order_id})
        if res['status'] == 'NEW':
            spot_order.status = OrderStatus.NEW
        elif res['status'] == 'FILLED':
            spot_order.status = OrderStatus.FILLED
        elif res['status'] == 'PARTIALLY_FILLED':
            spot_order.status = OrderStatus.PARTIALLY_FILLED
        else:
            spot_order.status = OrderStatus.CANCELED
        spot_order.quantity_cumulative = float(res['cummulativeQuoteQty'])
        spot_order.updated_at = res['updateTime']
        return spot_order
    
    async def _query_orders(self, spot_orders:List[SpotOrder]):
        if not spot_orders:
            return []
        else:
            data = []
            for spot_order in spot_orders:
                res = await self._query_order(spot_order)
                data.append(res)
            return data

    @time_out
    async def _curl(self, path: str, auth:bool=False, verb: str = None, query: dict = None, post_dict: dict = None, attribute: str = None, retry_count: int = 0):
        """Send a request to Server."""
        if not attribute:
            if not verb:
                verb = 'GET'
            headers = {'X-MBX-APIKEY': self._api_key}
            max_retries = self._retries
            timestamp = int(dt.datetime.now().timestamp()*1000)
            url = self._api_endpoint + path
            rcv_window = 10000
            if not query:
                query = {}
            query['recvWindow'] = rcv_window
            query['timestamp'] = timestamp
            query_string = urlencode(query)
            signature = _create_signature(self._secret_key,query_string)
            url += '?' + query_string + '&signature=' + signature
        else:
            verb = 'GET'
            headers = {}
            url = 'https://www.bitrue.com/kline-api/kline/history/' + query['symbol'] + '/market_meldusdt_kline_' + query['period']
            
        async def retry():
            r = await self._curl(path, auth, verb, query, post_dict, attribute, retry_count + 1)
            return r
        try:
            if verb == 'GET':
                async with self._session.get(url, headers=headers) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
            elif verb == 'POST':
                async with self._session.post(url, headers=headers) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
            elif verb == 'PATCH':
                async with self._session.patch(url, headers=headers) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
            elif verb == 'PUT':
                async with self._session.put(url, headers=headers) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
            elif verb == 'DELETE':
                async with self._session.delete(url, headers=headers) as resp:
                    resp.raise_for_status()
                    response = await resp.text()
        
        except aiohttp.ClientResponseError as e:
            self.logger.info(e)
            resp_status = resp.status
            # if resp_status == 500 or resp_status == 503:
            if resp_status > 200:
                if retry_count < max_retries:
                    self.logger.warning("Service unavailable. Retrying.")
                    return await retry()
                else:
                    return None
            else:
                raise e
        except Exception as e:
            self.logger.info(e)
            raise e
        return json.loads(response)
