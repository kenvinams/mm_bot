import asyncio
from asyncio.proactor_events import _ProactorBasePipeTransport
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps
import threading
import signal
import yaml
from yaml.loader import SafeLoader

import global_settings
from core.entities import Token, Pair, MarketInfo, Account
from core.exchange import SpotExchange
from strategies import StrategyBase

exit_event = threading.Event()

def silence_event_loop_closed(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except RuntimeError as e:
                if str(e) != 'Event loop is closed':
                    raise
    
        return wrapper

class ThreadExecutor:
    def __init__(self, loop, n_threads=8):
        self._ex = ThreadPoolExecutor(n_threads)
        self._loop = loop

    def __call__(self, f, *args, **kw):
        return self._loop.run_in_executor(self._ex, partial(f, *args, **kw))

class MarketMaker:

    def __init__(self, bot_id: int):
        self.bot_id = bot_id  # Record bot id for each specific purpose (combined strategy, exchange etc.)
        self.market_infos, self._strat_name = self.read_bot_profile(bot_id)
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
        # Start new event loop
        self._loop = None
        self.executor = None
        # Set result of future for a bot instance. Atm return none
        self._return = None

        # Others
        strategy_cls = StrategyBase.initialize_strategy(self._strat_name)
        self.strategy = strategy_cls(self.exchange_bases)
    
    def read_bot_profile(self, bot_id:int):
        with open('market_maker/bot_profiles.yaml', 'r') as f:
            config = yaml.load(f, Loader=SafeLoader)
        res = config.get(str(bot_id))
        if not res:
            raise ValueError(f'Not bot with id {bot_id} found.')
        else:
            strat = res['strategy_file']
            market_infos = []
            for m in res['exchange_bases']:
                pairs = []
                exchange_type = m['exchange_type']
                exchange_name = m['exchange_name']
                print(exchange_name)
                api_key = m['account']['api_key']
                secret_key = m['account']['secret_key']
                account = Account(api_key, secret_key)
                for p in m['pairs']:
                    pair = Pair(Token(p['base_asset']), Token(p['quote_asset']))
                    pairs.append(pair)
                market_info = MarketInfo(exchange_name,pairs,account)
                market_infos.append(market_info)
            return [market_infos, strat]

    def signal_handler(self, signum, frame):
        for exchange_base in self.exchange_bases:
            exchange_base.EXCHANGE_ENABLED = False
        del self.executor._ex._threads
        self._loop.close()

    async def _run(self):
        task_run_exchange_base = asyncio.create_task(self.exchange_base.run())
        await asyncio.gather(task_run_exchange_base, self.executor(self.strategy.run))

    def run(self):
        _ProactorBasePipeTransport.__del__ = silence_event_loop_closed(_ProactorBasePipeTransport.__del__)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        signal.signal(signal.SIGINT, self.signal_handler) # Handle exit signal
        self.executor = ThreadExecutor(self._loop, global_settings.MAX_NUM_THREADS)
        print(f'Start running bot id: {self.bot_id}')
        self._loop.run_until_complete(self._run())
        self._loop.close()
        return 'Bot finished running~~'  # Reserved for future of a bot instance

    async def exit(self):
        self.LOOP_ENABLED = False
        self.exchange_base.close()
