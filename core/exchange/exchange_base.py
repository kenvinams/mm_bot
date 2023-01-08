from abc import ABCMeta
from aiohttp import ClientSession
import asyncio
from enum import Enum, IntEnum
import json
from typing import List
import time

from core.entities import (
    Account,
    Pair,
    MarketInfo,
    SpotOrder,
    Inventory,
    TradeSide,
    OrderStatus,
)
from core import utils
from core.exchange.order_manger import OrderManager
from core.exchange.connector import BaseConnector
import global_settings


class MarketStatus(IntEnum):
    READY = 1
    NOT_READY = 0


class BasicStatus(IntEnum):
    READY = 1
    NOT_READY = 0


class ProcessingStatus(Enum):
    INITIALIZING = "INITIALIZING"
    PROCESSED = "PROCESSED"
    PROCESSING = "PROCESSING"
    PROCESSED_ERROR = "PROCESSED_ERROR"


class IExchange(metaclass=ABCMeta):
    def __init__(self, market_info: MarketInfo):
        # SETUP MARKET INFO TO INITIALIZE EXCHANGE
        self._market_info = market_info

        # EXCHANGE ATTRIBUTES
        self._exchange_name = None
        self._connector: BaseConnector = None
        self._account: Account = None

        # Others
        self.logger = utils.setup_custom_logger(__name__)
        self._exchange_start_time = time.perf_counter()
        self.WS_AVAILABLE = False
        self.READ_ONLY = False 
        self._pairs: List[Pair] = []
        self._trading_pairs: List = []
        self._active_spot_orders: List[SpotOrder] = []
        self._inventory: Inventory = None
        self._tokens = [] 
        self._api_key = None
        self._secret_key = None
        self._session = None
        self._start_time = time.perf_counter()
        self._time_passed = None 
        self._loop_start_time = None 
        self._pair = None
        self._trading_pair = None

        self._fetch_data_tasks = []
        self._additional_fetch_tasks = []
        self._action_process_tasks = []
        self._orders_post = []
        self._cancel_all_orders = False
        self._cancel_orders = []

        self.MARKET_READY = MarketStatus.NOT_READY
        self.FETCH_DATA_STATUS = ProcessingStatus.PROCESSING
        self.STRATEGY_CALCULATION_STATUS = ProcessingStatus.PROCESSING
        self.READY_FOR_STRATEGY = BasicStatus.NOT_READY
        self.HANDLE_UNFINISHED_TASKS = ProcessingStatus.PROCESSED
        self.PROCESS_ACTION_STATUS = ProcessingStatus.INITIALIZING
        self.MAIN_PROCESS_STATUS = ProcessingStatus.INITIALIZING
        self.EXCHANGE_ENABLED = True


class SpotExchange(IExchange):
    def __init__(self, market_info: MarketInfo):
        super().__init__(market_info)
        self._initialize(market_info)
        self._order_manager = OrderManager(self)

    @property
    def exchange_name(self):
        return self._exchange_name

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def tokens(self):
        return self._tokens

    @property
    def inventory(self):
        return self._inventory

    @property
    def get_active_spot_orders(self):
        return self._active_spot_orders

    @property
    def TIME_PASSED(self):
        return self._time_passed

    @property
    def pairs(self):
        return self._pairs

    @property
    def pair(self):
        return self._pair

    @property
    def trading_pair(self):
        return self._trading_pair

    @property
    def OrderManager(self):
        return self._order_manager

    async def run(self):
        await self._run()

    def change_strategy_status(
        self, status: ProcessingStatus = ProcessingStatus.PROCESSED
    ):
        self.STRATEGY_CALCULATION_STATUS = status

    def close(self):
        self.EXCHANGE_ENABLED = False
        self.logger.info(f"Exit exchange {self._exchange_name}...")

    def cancel_spot_orders(self, spot_orders: List[SpotOrder]):
        self.OrderManager._add_cancel_orders(spot_orders)

    def cancel_all_spot_orders(self):
        self.OrderManager._cancel_all_orders()
        self.logger.info("Cancel all spot orders.")

    def create_spot_order(self, spot_order: SpotOrder):
        """
        Create a single spot order. Should only use in case a single order post in an interval.
        :param spot_order: SpotOrder.
        :return: spot order created.
        """
        pair = spot_order.pair
        base_asset = pair.base_asset
        quote_asset = pair.quote_asset
        volume = spot_order.quantity
        price = spot_order.price
        spot_order.status = OrderStatus.NEW
        spot_order.order_id = self.OrderManager._create_id()
        if spot_order.side == TradeSide.BUY:
            if float(volume * price) * global_settings.BUFFER_ORDER_QUANTITY >= float(
                self.inventory.get_single_balance(quote_asset)
            ):
                self.logger.error(
                    f"Buy order quantity larger than current inventory: Order amount: "
                    f"{float(volume * price) * global_settings.BUFFER_ORDER_QUANTITY:.2f} while "
                    f"current {quote_asset} balance is {float(self.inventory.get_single_balance(quote_asset)):.2f}"
                )
                return False
        else:
            if (
                float(volume)
                > float(self.inventory.get_single_balance(base_asset))
                * global_settings.BUFFER_ORDER_QUANTITY
            ):
                self.logger.error(
                    f"Sell order quantity larger than current inventory: Order amount: "
                    f"{volume} while "
                    f"current {base_asset} balance is {float(self.inventory.get_single_balance(base_asset)):.2f}"
                )
                return False

        self.logger.info(
            f"Posting a {spot_order.side} {spot_order.order_type} "
            f"order of pair {pair.trading_pair} with volume {spot_order.quantity} and price {spot_order.price}"
        )
        self.OrderManager._add_post_orders([spot_order])

    def create_spot_orders(self, spot_orders: List[SpotOrder]):
        """
        Create multiple spot orders. Use in case when multiple order quoted in an interval.

        :param spot_orders: List[SpotOrder]
        :return: List of spot orders created.
        """
        # This will be written in numpy later to improve performance.
        self.logger.info(
            f"Try to create multiple orders on {self.exchange_name} Exchange."
        )
        list_trading_pairs = []
        for spot_order in spot_orders:
            p = spot_order.pair
            b = p.base_asset
            q = p.quote_asset
            list_trading_pairs.append((b, q))
            spot_order.order_id = self.OrderManager._create_id()
            spot_order.status = OrderStatus.NEW
        trading_pairs = list(set(list_trading_pairs))
        for p in trading_pairs:
            sum_buy = 0
            sum_sell = 0
            for spot_order in spot_orders:
                if spot_order.pair.trading_pair == p[0] + p[1]:
                    if spot_order.side == TradeSide.BUY:
                        sum_buy += spot_order.quantity * spot_order.price
                    else:
                        sum_sell += spot_order.quantity

            if float(
                sum_buy
            ) * global_settings.BUFFER_ORDER_QUANTITY >= self.inventory.get_single_balance(
                p[1]
            ):
                self.logger.error(
                    f"Buy order quantity for pair {p[0] + p[1]} larger than current inventory. "
                    f"Buy volume: {float(sum_buy) * global_settings.BUFFER_ORDER_QUANTITY}"
                )
                return False
            if float(
                sum_sell
            ) > global_settings.BUFFER_ORDER_QUANTITY * self.inventory.get_single_balance(
                p[0]
            ):
                self.logger.error(
                    f"Sell order quantity for pair {p[0] + p[1]} larger than current inventory. "
                    f"Sell volume: {sum_sell}"
                )
                return False

        for spot_order in spot_orders:
            self.logger.info(
                f"Posting a {spot_order.side} {spot_order.order_type} "
                f"order of pair {spot_order.pair.trading_pair} with volume {spot_order.quantity} and price {spot_order.price}"
            )
        self.OrderManager._add_post_orders(spot_orders)

    async def _run(self):
        async with ClientSession() as self._connector._session:
            while self.EXCHANGE_ENABLED:
                tasks = []
                st_time = time.perf_counter()
                loop_sleep = asyncio.create_task(self._loop_interval())
                task_fetch_data = asyncio.create_task(self._fetch_data_process())
                task_process_action = asyncio.create_task(
                    self._handle_strategy_action()
                )
                tasks.append(loop_sleep)
                tasks.append(task_fetch_data)
                tasks.append(task_process_action)
                await asyncio.gather(*tasks)
                self._time_passed = time.perf_counter() - self._start_time
                print(f"Time passed: {time.perf_counter() - st_time:.2f}s")

    async def _handle_strategy_action(self):
        while self.MAIN_PROCESS_STATUS == ProcessingStatus.PROCESSING:
            await asyncio.sleep(0.001)
            if self.MARKET_READY:
                if self.FETCH_DATA_STATUS == ProcessingStatus.PROCESSED:
                    self.READY_FOR_STRATEGY = BasicStatus.READY
                    if self.STRATEGY_CALCULATION_STATUS == ProcessingStatus.PROCESSED:
                        if (len(self.OrderManager._initialized_orders) < 1) and (
                            len(self.OrderManager._cancelled_orders_list) < 1
                        ):
                            self.PROCESS_ACTION_STATUS = ProcessingStatus.PROCESSED
                            self.READY_FOR_STRATEGY = BasicStatus.NOT_READY
                            return True
                        else:
                            self.READY_FOR_STRATEGY = BasicStatus.NOT_READY
                            tasks = []
                            task = asyncio.create_task(
                                self._connector.cancel_spot_orders(
                                    self.OrderManager._cancelled_orders_list
                                )
                            )
                            tasks.append(task)
                            task = asyncio.create_task(
                                self._connector.create_spot_orders(
                                    self.OrderManager._initialized_orders
                                )
                            )
                            tasks.append(task)
                            orders_cancelled = await tasks[0]
                            orders_post = await tasks[1]
                            self.OrderManager._cancelling_orders()  # Transfer cancelling orders
                            self.OrderManager._posting_orders()  # Transfer posting orders
                            self.OrderManager._cancelled_orders(orders_cancelled)
                            self.OrderManager._posted_orders(orders_post)
                            return True
                    else:
                        self.PROCESS_ACTION_STATUS = ProcessingStatus.PROCESSING
                elif self.FETCH_DATA_STATUS == ProcessingStatus.PROCESSING:
                    self.READY_FOR_STRATEGY = BasicStatus.NOT_READY
                    self.PROCESS_ACTION_STATUS = ProcessingStatus.PROCESSING
                else:
                    self.READY_FOR_STRATEGY = BasicStatus.NOT_READY
                    self.PROCESS_ACTION_STATUS = ProcessingStatus.PROCESSING
                    return False

    async def _fetch_data_process(self):
        tasks = []
        self.FETCH_DATA_STATUS = ProcessingStatus.PROCESSING
        if not self.MARKET_READY:
            task = asyncio.create_task(self._connector.get_inventory_balance())
            tasks.append(task)
            task = asyncio.create_task(self._connector.get_order_book())
            tasks.append(task)
            task = asyncio.create_task(self._connector.get_trading_candles())
            tasks.append(task)
            task = asyncio.create_task(self._connector.get_tickers())
            tasks.append(task)
            task = asyncio.create_task(self._connector.get_active_spot_orders())
            tasks.append(task)
            inventory_res = await tasks[0]
            orderbook_res = await tasks[1]
            candles_res = await tasks[2]
            tickers_res = await tasks[3]
            active_orders_res = await tasks[4]
            if tickers_res is None:
                self.logger.warning("Market not ready, no tickers data. Retrying...")
                return False
            if candles_res is None:
                self.logger.warning("Market not ready, no candles data. Retrying...")
                return False
            if orderbook_res is None:
                self.logger.warning("Market not ready, no orderbook data. Retrying...")
                return False
            if inventory_res is None:
                self.logger.warning("Market not ready, no inventory data. Retrying...")
                return False
            if active_orders_res is None:
                self.logger.warning(
                    "Market not ready, no active orders data. Retrying..."
                )
                return False
            # Set maker and taker rates, orderbooks, trading candles, tickers.
            for pair in self._pairs:
                pair._add_orderbook(orderbook_res.get(pair.trading_pair))
                pair._add_trading_candles(candles_res.get(pair.trading_pair))
                pair._add_tickers(tickers_res.get(pair.trading_pair))
            # Update inventory
            self._inventory.update_inventory(inventory_res)
            # Update active orders
            self.OrderManager._insert_active_orders(active_orders_res)
            self.MARKET_READY = MarketStatus.READY
            self.logger.info(f"Exchange {self.exchange_name} ready.")
            self.FETCH_DATA_STATUS = ProcessingStatus.PROCESSED
            return True
        else:
            task = asyncio.create_task(self._connector.get_inventory_balance())
            tasks.append(task)
            task = asyncio.create_task(self._connector.get_order_book())
            tasks.append(task)
            task = asyncio.create_task(self._connector.get_trading_candles())
            tasks.append(task)
            task = asyncio.create_task(self._connector.get_tickers())
            tasks.append(task)
            task = asyncio.create_task(
                self._connector.query_orders(self.OrderManager._tracked_orders)
            )
            tasks.append(task)

            inventory_res = await tasks[0]
            orderbook_res = await tasks[1]
            candles_res = await tasks[2]
            tickers_res = await tasks[3]
            tracked_orders_res = await tasks[4]

            if inventory_res is None:
                self.logger.warning("Market not ready, no inventory data. Retrying...")
                return False
            else:
                self._inventory.update_inventory(inventory_res)

            if len(orderbook_res) > 0:
                for pair in self._pairs:
                    pair._add_orderbook(orderbook_res.get(pair.trading_pair))
            else:
                self.logger.warning("No data for orderbook.")

            if len(candles_res) > 0:
                for pair in self._pairs:
                    pair._add_trading_candles(candles_res.get(pair.trading_pair))
            else:
                self.logger.warning("No data for candles.")

            if len(tickers_res) > 0:
                for pair in self._pairs:
                    pair._add_tickers(tickers_res.get(pair.trading_pair))
            else:
                self.logger.warning("No data for tickers.")
            self.OrderManager._update_state(tracked_orders_res)

            self.FETCH_DATA_STATUS = ProcessingStatus.PROCESSED
            return True

    async def _loop_interval(self):
        self._loop_start_time = time.perf_counter()
        self.logger.debug("Start new loop")
        self.MAIN_PROCESS_STATUS = ProcessingStatus.PROCESSING
        self.STRATEGY_CALCULATION_STATUS = ProcessingStatus.PROCESSING
        self.READY_FOR_STRATEGY = BasicStatus.NOT_READY
        await asyncio.sleep(global_settings.LOOP_INTERVAL)
        self.MAIN_PROCESS_STATUS = ProcessingStatus.PROCESSED
        self.logger.debug("End loop")
        return 1

    def _initialize(self, market_info: MarketInfo):
        """Initialize Exchange_Base

        Args:
            market_info (MarketInfo): market info.
        """
        self._exchange_name = market_info.exchange
        self._init_connector(market_info.exchange)
        self._subscribe_pair(market_info.pairs)
        self._register_account(market_info.account)
        self._configure_exchange(self._exchange_name)

    def _init_connector(self, exchange_name: str):
        """Initialize BaseConnector.

        Args:
            exchange_name (str): name of exchange.
        """
        connector = BaseConnector._initialize_connector(exchange_name)
        self._connector = connector()
        # self.WS_AVAILABLE = self._connector._ws_available

    def _configure_exchange(self, exchange_name: str):
        """

        :param exchange_name: exchange name
        """
        with open(f"core/exchange/config/{exchange_name}_settings.json") as f:
            data = json.load(f)
        for p in self.pairs:
            d = data[p.trading_pair]
            p._set_rate((float(d["take_rate"]), float(d["make_rate"])))
            p.quantity_increment = float(d["quantity_increment"])
            p.tick_size = float(d["tick_size"])

    def _subscribe_pair(self, pairs: List[Pair]):
        """Add pairs (cls) and trading_pairs.
        Args:
            pairs (List[Pair]): List of Pair to add.
        """
        for p in pairs:
            self._pairs.append(p)
            self._trading_pairs.append(p.trading_pair)
            self._tokens.append(p.base_asset)
            self._tokens.append(p.quote_asset)
        self._pairs = tuple(self._pairs)
        self._trading_pairs = tuple(self._trading_pairs)
        self._tokens = list(set(self._tokens))
        self._inventory = Inventory(self._tokens)
        if len(self._pairs) < 2:
            self._pair = self._pairs[0]
            self._trading_pair = self._trading_pairs[0]
        self._connector._pairs = self._pairs
        self._connector._trading_pairs = self._trading_pairs
        self._connector._tokens = self._tokens

    def _register_account(self, account: Account):
        """Register exchange account information.

        Args:
            account (Account): Account.
        """
        self._account = account
        self._api_key, self._secret_key = account.get_login_info()
        self._connector.register_account(account)

    def _login_information(self):
        """Get login information.
        Returns:
            Tuple(api_key, secret_key)
        """
        return self._account.get_login_info()
