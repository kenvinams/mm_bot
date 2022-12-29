class OrderException(Exception):
    pass

class InsufficientOrdersException(OrderException):
    """Number of active orders return less than active orders being tracked.
    """
    pass

class OrdersUpdateFailException(OrderException):
    pass