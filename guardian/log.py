import sys
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


class Log(sys.modules[__name__].__class__):
    def init(self, level: str):
        level = level.upper()
        if level not in logging._nameToLevel:
            raise ValueError('Unknown logging level: %r' % level)

        self.level = logging._nameToLevel[level]
        self.lgr = logging.getLogger()
        self.lgr.setLevel(self.level)
        ch = logging.StreamHandler()
        ch.setLevel(self.level)
        ch.setFormatter(Formatter())
        self.lgr.addHandler(ch)
        return self.lgr

    def get_logger(self):
        if getattr(self, 'lgr', None) is None:
            raise RuntimeError('Logger was not initialized')
        return self.lgr

    logger = property(get_logger)


sys.modules[__name__].__class__ = Log
