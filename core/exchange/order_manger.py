import uuid
from enum import Enum
from typing import List

from core.entities import SpotOrder, OrderStatus, Pair
from core.utils.exception import InsufficientOrdersException
import global_settings


class ActiveStatus(Enum):
    INITIALIZED = "INITIALIZED"
    HANGING_POSTING = "HANGING_POSTING"
    ACTIVE = "ACTIVE"
    CANCELLED_LIST = "CANCELLED_LIST"
    HANGING_CANCELLING = "HANGING_CANCELLING"
    COMPLETED = "COMPLETED"


class SubOrderManager:
    def __init__(self, pair: Pair):
        self._pair = pair
        self._orders = {status: {} for status in ActiveStatus}
        self._order_active_status = {}
        self._tracked_orders = {}
        self._back_log = {}

    @property
    def pair(self) -> Pair:
        return self._pair

    @property
    def hanging_posting_orders(self) -> List[SpotOrder]:
        return list(self._orders[ActiveStatus.HANGING_POSTING].values())

    @property
    def hanging_cancelling_orders(self) -> List[SpotOrder]:
        return list(self._orders[ActiveStatus.HANGING_CANCELLING].values())

    @property
    def active_orders(self) -> List[SpotOrder]:
        return list(self._orders[ActiveStatus.ACTIVE].values())

    @property
    def back_log_orders(self) -> List[SpotOrder]:
        return list(self._back_log.values())

    @property
    def _completed_orders(self) -> List[SpotOrder]:
        return list(self._orders[ActiveStatus.COMPLETED].values())

    @property
    def _initialized_orders(self) -> List[SpotOrder]:
        return list(self._orders[ActiveStatus.INITIALIZED].values())

    @property
    def _cancelled_orders(self) -> List[SpotOrder]:
        return list(self._orders[ActiveStatus.CANCELLED_LIST].values())

    @property
    def tracked_orders(self) -> List[SpotOrder]:
        return list(self._tracked_orders.values())

    def _add_post_order(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            for spot_order in spot_orders:
                order_id = spot_order.order_id
                self._orders[ActiveStatus.INITIALIZED][order_id] = spot_order
                self._order_active_status[order_id] = ActiveStatus.INITIALIZED

    def _posting_order(self):
        spot_orders = self._initialized_orders
        if not spot_orders:
            return
        else:
            for spot_order in spot_orders:
                self.__change_state(spot_order, ActiveStatus.HANGING_POSTING)

    def _posted_order(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            for spot_order in spot_orders:
                status = spot_order.status
                if status != OrderStatus.CANCELED or status != OrderStatus.FILLED:
                    self.__change_state(spot_order, ActiveStatus.ACTIVE)
                    self._tracked_orders[spot_order.order_id] = spot_order
                else:
                    self.__change_state(spot_order, ActiveStatus.COMPLETED)
            if len(self._orders[ActiveStatus.HANGING_POSTING]) > 0:
                for spot_order in self.hanging_posting_orders:
                    self.__change_state(spot_order, ActiveStatus.INITIALIZED)

    def _add_cancel_order(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            for spot_order in spot_orders:
                order_id = spot_order.order_id
                current_state = self._order_active_status[order_id]
                if current_state == ActiveStatus.ACTIVE:
                    self.__change_state(spot_order, ActiveStatus.CANCELLED_LIST)

    def _cancel_all_orders(self):
        self._add_cancel_order(self.active_orders)

    def _cancelling_order(self):
        spot_orders = self._cancelled_orders
        if not spot_orders:
            return
        else:
            for spot_order in spot_orders:
                self.__change_state(spot_order, ActiveStatus.HANGING_CANCELLING)

    def _cancelled_order(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            for spot_order in spot_orders:
                self.__change_state(spot_order, ActiveStatus.COMPLETED)
                self._tracked_orders.pop(spot_order.order_id)
            if len(self._orders[ActiveStatus.HANGING_CANCELLING]) > 0:
                for spot_order in self.hanging_cancelling_orders:
                    self.__change_state(spot_order, ActiveStatus.CANCELLED_LIST)

    def __change_state(self, spot_order: SpotOrder, target_state: ActiveStatus):
        """Change state of an order in order manager.
        Args:
            spot_order (SpotOrder): an existing spot order.
            target_state (ActiveStatus): target order state.
        """
        order_id = spot_order.order_id
        current_state = self._order_active_status[order_id]
        if current_state == target_state:
            return
        else:
            self._orders[target_state][order_id] = spot_order
            self._orders[current_state].pop(order_id)
            self._order_active_status[order_id] = target_state

    def _add_backlog(self, spot_orders: List[SpotOrder] = [], all: bool = False):
        if all:
            if len(self.active_orders) > 0:
                for spot_order in self.active_orders:
                    spot_order.quantity = (
                        spot_order.quantity - spot_order.quantity_cumulative
                    )
                    spot_order.quantity_cumulative = 0
                    self._back_log[spot_order.order_id] = spot_order
                self._cancel_all_orders()
            else:
                return
        else:
            if not spot_orders:
                return
            else:
                list_orders = []
                for spot_order in spot_orders:
                    order_id = spot_order.order_id
                    current_state = self._order_active_status[order_id]
                    if current_state == ActiveStatus.ACTIVE:
                        spot_order.quantity = (
                            spot_order.quantity - spot_order.quantity_cumulative
                        )
                        spot_order.quantity_cumulative = 0
                        self._back_log[spot_order.order_id] = spot_order
                        list_orders.append(spot_order)
                self._add_cancel_order(list_orders)

    def _backlog_recover(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            for spot_order in spot_orders:
                order_id = spot_order.order_id
                self._back_log.pop(order_id)

    def update_state(self, spot_orders: List[SpotOrder]):
        """Update states of all or some spot_orders at each interval.
        Args:
            spot_orders (List[SpotOrder]): list of Spot Orders.
        """
        if not spot_orders:
            return
        for spot_order in spot_orders:
            if spot_order is None:
                raise InsufficientOrdersException
            order_id = spot_order.order_id
            current_state = self._order_active_status[order_id]
            if current_state == ActiveStatus.CANCELLED_LIST:
                if (
                    spot_order.status == OrderStatus.CANCELED
                    or spot_order.status == OrderStatus.FILLED
                ):
                    self.__change_state(spot_order, ActiveStatus.COMPLETED)
                    self._tracked_orders.pop(order_id)
            elif current_state == ActiveStatus.ACTIVE:
                if (
                    spot_order.status == OrderStatus.CANCELED
                    or spot_order.status == OrderStatus.FILLED
                ):
                    self.__change_state(spot_order, ActiveStatus.COMPLETED)
                    self._tracked_orders.pop(order_id)
                else:
                    self._orders[current_state][order_id] = spot_order

    def insert_active_orders(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        for spot_order in spot_orders:
            order_id = spot_order.order_id
            self._orders[ActiveStatus.ACTIVE][order_id] = spot_order
            self._order_active_status[order_id] = ActiveStatus.ACTIVE
            self._tracked_orders[order_id] = spot_order


class OrderManager:
    def __init__(self, exchange_base):
        self._exchange_base = exchange_base
        self._pairs = exchange_base.pairs
        self._sub_OMs = {pair: SubOrderManager(pair) for pair in self._pairs}
        self._exchange_name = exchange_base.exchange_name
        self._ws_available = self._exchange_base.WS_AVAILABLE
        self._orders = {status: {} for status in ActiveStatus}
        self._order_active_status = {}

    @property
    def _sub_order_managers(self):
        """Return sub OrderManager class of each pair."""
        return self._sub_OMs.values()

    @property
    def active_orders(self) -> List[SpotOrder]:
        """Return all current active orders."""
        spot_orders = []
        for om in self._sub_order_managers:
            spot_orders.extend(om.active_orders)
        return spot_orders

    @property
    def back_log_orders(self) -> List[SpotOrder]:
        """Return all backlog orders."""
        spot_orders = []
        for om in self._sub_order_managers:
            spot_orders.extend(om.back_log_orders)
        return spot_orders

    @property
    def _tracked_orders(self) -> List[SpotOrder]:
        spot_orders = []
        for om in self._sub_order_managers:
            spot_orders.extend(om.tracked_orders)
        return spot_orders

    @property
    def _initialized_orders(self) -> List[SpotOrder]:
        spot_orders = []
        for om in self._sub_order_managers:
            spot_orders.extend(om._initialized_orders)
        return spot_orders

    @property
    def _cancelled_orders_list(self) -> List[SpotOrder]:
        spot_orders = []
        for om in self._sub_order_managers:
            spot_orders.extend(om._cancelled_orders)
        return spot_orders

    @property
    def _completed_orders(self) -> List[SpotOrder]:
        """Return all completed orders."""
        spot_orders = []
        for om in self._sub_order_managers:
            spot_orders.extend(om._completed_orders)
        return spot_orders

    def __get_subOM(self, pair: Pair) -> SubOrderManager:
        return self._sub_OMs[pair]

    def __divide_orders(self, spot_orders: List[SpotOrder]):
        di = {pair: [] for pair in self._pairs}
        for spot_order in spot_orders:
            if spot_order is not None:
                pair = spot_order.pair
                di[pair].append(spot_order)
        return di

    def add_backlog(self, spot_orders: List[SpotOrder] = [], all: bool = False):
        """Add orders to backlog to use later.

        Args:
            spot_orders (List[SpotOrder]): List of Spot Order to put into backlog.
            all (bool): True to add all active orders to backlog, default: False.
        """
        if all:
            for om in self._sub_order_managers:
                om._add_backlog(all=True)
        else:
            if not spot_orders:
                return
            else:
                dict_orders = self.__divide_orders(spot_orders)
                for pair in self._pairs:
                    self.__get_subOM(pair)._add_backlog(dict_orders[pair])

    def recover_backlog(self, spot_orders: List[SpotOrder] = [], all: bool = False):
        """Recover backlog orders (put into active).

        Args:
            spot_orders (List[SpotOrder]): List of Spot Order to put back.
            all (bool): True to recover all backlog orders to active, default: False.
        """
        if all:
            if len(self.back_log_orders) > 0:
                self._exchange_base.create_spot_orders(self.back_log_orders)
                for om in self._sub_order_managers:
                    om._back_log = {}
            else:
                return
        else:
            self._exchange_base.create_spot_orders(spot_orders)
            dict_orders = self.__divide_orders(spot_orders)
            for pair in self._pairs:
                self.__get_subOM(pair)._backlog_recover(dict_orders[pair])

    def _add_post_orders(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            dict_orders = self.__divide_orders(spot_orders)
            for pair in self._pairs:
                self.__get_subOM(pair)._add_post_order(dict_orders[pair])

    def _posting_orders(self):
        for om in self._sub_order_managers:
            om._posting_order()

    def _posted_orders(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            dict_orders = self.__divide_orders(spot_orders)
            for pair in self._pairs:
                self.__get_subOM(pair)._posted_order(dict_orders[pair])

    def _add_cancel_orders(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            dict_orders = self.__divide_orders(spot_orders)
            for pair in self._pairs:
                self.__get_subOM(pair)._add_cancel_order(dict_orders[pair])

    def _cancel_all_orders(self):
        for om in self._sub_order_managers:
            om._cancel_all_orders()

    def _cancelling_orders(self):
        for om in self._sub_order_managers:
            om._cancelling_order()

    def _cancelled_orders(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            dict_orders = self.__divide_orders(spot_orders)
            for pair in self._pairs:
                self.__get_subOM(pair)._cancelled_order(dict_orders[pair])

    def _update_state(self, spot_orders: List[SpotOrder]):
        """Update states of all or some spot_orders at each interval.
        Args:
            spot_orders (List[SpotOrder]): list of Spot Orders.
        """
        if not spot_orders:
            return
        else:
            dict_orders = self.__divide_orders(spot_orders)
            for pair in self._pairs:
                self.__get_subOM(pair).update_state(dict_orders[pair])

    def _insert_active_orders(self, spot_orders: List[SpotOrder]):
        if not spot_orders:
            return
        else:
            dict_orders = self.__divide_orders(spot_orders)
            for pair in self._pairs:
                self.__get_subOM(pair).insert_active_orders(dict_orders[pair])

    def _create_id(self):
        """
        Create unique client order id to manage internally.
        """
        order_id = (
            global_settings.CLIENT_ORDER_PREFIX
            + self._exchange_name.lower()
            + "_"
            + str(uuid.uuid1()).replace("-", "")[: -(6 + len(self._exchange_name))]
        )
        return order_id

    def __call__(self, pair: Pair) -> SubOrderManager:
        return self._sub_OMs[pair]
