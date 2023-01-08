import logging
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
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.setLevel(log_level)
    logger.addHandler(handler)
    return logger
