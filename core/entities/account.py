from typing import List

class Account:

    def __init__(self, api_key: str,
                 secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
    
    def get_login_info(self):
        return tuple([self.api_key, self.secret_key])
