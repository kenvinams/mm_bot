from concurrent.futures import ProcessPoolExecutor
from market_maker import MarketMaker


def main():
    num_thread = 8
    with ProcessPoolExecutor(num_thread) as executor:
        bots_list = []
        simple_bot = MarketMaker(5)
        bots_list.append(simple_bot)
        futures = [executor.submit(b.run) for b in bots_list]


if __name__ == '__main__':
    main()
