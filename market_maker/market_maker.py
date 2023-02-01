import asyncio
from asyncio.proactor_events import _ProactorBasePipeTransport
from enum import Enum, IntEnum
from functools import wraps
import time
import yaml
from yaml.loader import SafeLoader

from core.entities import Token, Pair, MarketInfo, Account
from core.exchange import SpotExchange
from core import utils
from strategies import StrategyBase
import global_settings


def silence_event_loop_closed(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except RuntimeError as e:
            if str(e) != "Event loop is closed":
                raise

    return wrapper

class BasicStatus(IntEnum):
    READY = 1
    NOT_READY = 0
    
class ProcessingStatus(Enum):
    INITIALIZING = "INITIALIZING"
    PROCESSED = "PROCESSED"
    PROCESSING = "PROCESSING"
    PROCESSED_ERROR = "PROCESSED_ERROR"

class MarketMaker:
    def __init__(self, bot_id: int):
        self.bot_id = bot_id
        self.market_infos, self._strat_name = self.read_bot_profile(bot_id)
        self._loop = None
        self.logger = utils.setup_custom_logger(__name__)
        self._running = True
        self.multiple_accounts_mode = False
        self.multiple_exchanges_mode = False
        self.exchange_bases = []

        for market_info in self.market_infos:
            exchange_base = SpotExchange(market_info)
            self.exchange_bases.append(exchange_base)

        if len(self.market_infos) < 2:
            self.market_info = self.market_infos[0]
            self.exchange_base = self.exchange_bases[0]

        strategy_cls = StrategyBase.initialize_strategy(self._strat_name)
        self.strategy = strategy_cls(self.exchange_bases)

    def read_bot_profile(self, bot_id: int):
        with open("./bot_profiles.yaml", "r") as f:
            config = yaml.load(f, Loader=SafeLoader)
        res = config.get(str(bot_id))
        if not res:
            raise ValueError(f"Bot id {bot_id} not found.")
        else:
            strat = res["strategy_file"]
            market_infos = []
            for m in res["exchange_bases"]:
                pairs = []
                exchange_type = m["exchange_type"]
                exchange_name = m["exchange_name"]
                api_key = m["account"]["api_key"]
                secret_key = m["account"]["secret_key"]
                account = Account(api_key, secret_key)
                for p in m["pairs"]:
                    pair = Pair(Token(p["base_asset"]), Token(p["quote_asset"]))
                    pairs.append(pair)
                market_info = MarketInfo(exchange_name, pairs, account)
                market_infos.append(market_info)
            return [market_infos, strat]

    async def _run(self):
        tasks = []
        while self._running:
            task_run_exchange = asyncio.create_task(self.exchange_base.run())
            tasks.append(task_run_exchange)
            await asyncio.gather(*tasks)
    
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

    def run(self):
        _ProactorBasePipeTransport.__del__ = silence_event_loop_closed(
            _ProactorBasePipeTransport.__del__
        )
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        print(f"Start running bot id: {self.bot_id}")
        self._loop.run_until_complete(self._run())
        self._loop.close()
        