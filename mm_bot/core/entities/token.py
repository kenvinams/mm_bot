class Token:
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()

    def __str__(self) -> str:
        return self.symbol
