import asyncio
from asyncio.proactor_events import _ProactorBasePipeTransport
from functools import wraps
import yaml
from yaml.loader import SafeLoader

import global_settings
from core.entities import Token, Pair, MarketInfo, Account
from core.exchange import SpotExchange
from strategies import StrategyBase


def silence_event_loop_closed(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except RuntimeError as e:
            if str(e) != "Event loop is closed":
                raise

    return wrapper


class MarketMaker:
    def __init__(self, bot_id: int):
        self.bot_id = bot_id
        self.market_infos, self._strat_name = self.read_bot_profile(bot_id)
        self._running = True
        self.exchange_bases = []
        self.order_manager = {}
        for market_info in self.market_infos:
            exchange_base = SpotExchange(market_info)
            self.exchange_bases.append(exchange_base)

        if len(self.market_infos) < 2:
            self.market_info = self.market_infos[0]
            self.exchange_base = self.exchange_bases[0]
        else:
            self.market_info = None
            self.exchange_base: SpotExchange = None
        self._loop = None

        strategy_cls = StrategyBase.initialize_strategy(self._strat_name)
        self.strategy = strategy_cls(self.exchange_bases)

    def read_bot_profile(self, bot_id: int):
        with open("market_maker/bot_profiles.yaml", "r") as f:
            config = yaml.load(f, Loader=SafeLoader)
        res = config.get(str(bot_id))
        if not res:
            raise ValueError(f"Not bot with id {bot_id} found.")
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

    def run(self):
        _ProactorBasePipeTransport.__del__ = silence_event_loop_closed(
            _ProactorBasePipeTransport.__del__
        )
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        print(f"Start running bot id: {self.bot_id}")
        self._loop.run_until_complete(self._run())
        self._loop.close()
        