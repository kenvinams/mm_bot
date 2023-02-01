import datetime


class OrderBook:
    def __init__(self, bids, asks, timestamp: datetime.datetime.timestamp):
        self._bids = sorted(bids)[::-1]
        self._asks = sorted(asks)
        self._timestamp = timestamp

    @property
    def bids(self):
        return self._bids

    @property
    def asks(self):
        return self._asks

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def get_best_bid(self):
        if len(self._bids) > 0:
            return self._bids[0][0]
        else:
            return None

    @property
    def get_best_ask(self):
        if len(self._asks) > 0:
            return self._asks[0][0]
        else:
            return None

    def get_nth_best_bid(self, n):
        if len(self._bids) > 0:
            if len(self._bids) >= n + 1:
                return self._bids[n][0]
            else:
                return self._bids[(len(self._bids)) - 1][0]
        else:
            return None

    def get_nth_best_ask(self, n):
        if len(self._asks) > 0:
            if len(self._asks) >= n + 1:
                return self._asks[n][0]
            else:
                return self._asks[(len(self._asks)) - 1][0]
        else:
            return None

    @property
    def get_mid_price(self):
        if self.get_best_ask is not None and self.get_best_bid is not None:
            return (self.get_best_ask + self.get_best_bid) / 2
        else:
            return None
