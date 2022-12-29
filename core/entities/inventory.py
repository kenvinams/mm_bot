import datetime as dt
from typing import List

import global_settings


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    def __getattr__(self, attr):
        return self.get(attr)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

class Inventory():
    def __init__(self,
                 tokens: List[str]):
        self._tokens = tokens
        self.max_length = global_settings.DATA_MAX_LENGTH
        self._current_token_balance = {token: 0 for token in tokens}
        self._all_token_balance: List = []

    def update_inventory(self, inventory: dict):
        for token in self._tokens:
            self._current_token_balance[token] = inventory.get(token, 0)
            if len(self._all_token_balance) < self.max_length:
                self._all_token_balance.append(
                    [dt.datetime.now(dt.timezone.utc).timestamp(), self._current_token_balance])
            else:
                self._all_token_balance = self._all_token_balance[1:] + [
                    [dt.datetime.now(dt.timezone.utc).timestamp(), self._current_token_balance]]

    @property
    def get_all_balances(self):
        """
        Get all balances with timestamp.

        Returns:
        balances List[List[timestamp, dict]]: List of all token balances with timestamp.
        """
        return self._all_token_balance

    @property
    def get_current_balances(self):
        """
        Get current balances for all tokens.

        Returns:
        current_balances (dict): tokens with current balance.
        """
        return dotdict(self._current_token_balance)

    def get_single_balance(self, symbol: str):
        """
        Get current available balance for a single token.

        Returns:
        symbol_balance (float): current available balance.
        """
        return self._current_token_balance[symbol]