import logging


class Formatter(logging.Formatter):
    green = '\x1b[32;20m'
    yellow = '\x1b[33;20m'
    red = '\x1b[31;20m'
    bold_red = '\x1b[31;1m'
    reset = '\x1b[0m'
    fmt = '%(name)s:%(message)s'

    FORMATS = {
        logging.DEBUG: logging.BASIC_FORMAT,
        logging.INFO: f'{green}%(levelname)s{reset}:{fmt}',
        logging.WARNING: f'{yellow}%(levelname)s{reset}:{fmt}',
        logging.ERROR: f'{red}%(levelname)s{reset}:{fmt}',
        logging.CRITICAL: f'{bold_red}%(levelname)s{reset}:{fmt}'
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logger = logging.getLogger()
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(Formatter())
logger.addHandler(ch)
