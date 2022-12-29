from abc import ABCMeta, abstractmethod
import importlib
import logging
from typing import List

from core.exchange import SpotExchange, ProcessingStatus, BasicStatus


class StrategyBase(metaclass=ABCMeta):
    def __init__(self, exchange_bases: List[SpotExchange]):
        self.exchange_bases = exchange_bases
        if len(self.exchange_bases) < 2:
            self.exchange_base: SpotExchange = exchange_bases[0]

        # Work on single exchange first

    @classmethod
    def initialize_strategy(cls, strategy_name: str):
        cls_name = cls.__name__
        if cls_name != 'StrategyBase':
            return
        else:
            try:
                module = importlib.import_module(f'strategies.{strategy_name}_strategy')
                strategy = getattr(module, 'StrategyCls')
                return strategy
            except (ImportError, AttributeError):
                raise ValueError(f'No strategy {strategy_name} existed.')

    def run(self):
        logging.basicConfig(filename='orders.log', filemode='a', level=logging.INFO,
                            format='%(asctime)s %(name)s - %(levelname)s - %(message)s')
        while all([exchange_base.EXCHANGE_ENABLED for exchange_base in self.exchange_bases]):
            strategy_ready = [exchange_base.READY_FOR_STRATEGY == BasicStatus.READY for exchange_base in self.exchange_bases]
            if all(strategy_ready):
                self._run()
                for exchange_base in self.exchange_bases:
                    exchange_base.change_strategy_status()
                    exchange_base.READY_FOR_STRATEGY = BasicStatus.NOT_READY

    @abstractmethod
    def _run(self):
        pass