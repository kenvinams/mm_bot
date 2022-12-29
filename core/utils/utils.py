import asyncio
from decimal import Decimal
from functools import wraps

import global_settings


def to_nearest(num, tickSize):
    """Given a number, round it to the nearest tick. Very useful for sussing float error
       out of numbers: e.g. toNearest(401.46, 0.01) -> 401.46, whereas processing is
       normally with floats would give you 401.46000000000004.
       Use this after adding/subtracting/multiplying numbers."""
    tickDec = Decimal(str(tickSize))
    return (Decimal(round(num / tickSize, 0)) * tickDec)

def time_out(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.create_task(asyncio.wait_for((func(*args, **kwargs)), timeout=global_settings.TIME_OUT_PROCESS))
            except asyncio.TimeoutError:
                return None
        return wrapper