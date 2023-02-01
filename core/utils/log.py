import logging
from logging.handlers import TimedRotatingFileHandler
import global_settings

loggers = {}


def setup_custom_logger(name, log_level=global_settings.LOG_LEVEL):
    if loggers.get(name):
        return loggers[name]
    logger = logging.getLogger(name)
    loggers[name] = logger
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(module)s - %(message)s"
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    file_handler = logging.FileHandler("orders.log")
    file_handler.setFormatter(formatter)
    logger.setLevel(log_level)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
