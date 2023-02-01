class OrderException(Exception):
    pass

class StrategyException(Exception):
    pass

class InsufficientOrdersException(OrderException):
    """Number of active orders return less than active orders being tracked."""

    pass


class OrdersUpdateFailException(OrderException):
    pass

class StrategyNoExistException(StrategyException):
    pass

class CalculationFailException(StrategyException):
    pass