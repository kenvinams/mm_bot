from enum import Enum, IntEnum

class MarketStatus(IntEnum):
    READY = 1
    NOT_READY = 0


class BasicStatus(IntEnum):
    READY = 1
    NOT_READY = 0


class ProcessingStatus(Enum):
    INITIALIZING = "INITIALIZING"
    PROCESSED = "PROCESSED"
    PROCESSING = "PROCESSING"
    PROCESSED_ERROR = "PROCESSED_ERROR"
    
