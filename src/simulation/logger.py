import logging
from logging import handlers
from datetime import timedelta


class RuntimeFormatter(logging.Formatter):

    def __init__(self, start_time, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = start_time

    def formatTime(self, record, datefmt=None):
        elapsed_seconds = record.created - self.start_time
        # Using timedelta here for convenient default formatting
        elapsed = timedelta(seconds = elapsed_seconds)
        return "{}".format(elapsed)


def configure_listener(logfile, start_time):
    root = logging.getLogger()
    file_handler = handlers.RotatingFileHandler(logfile)
    console_handler = logging.StreamHandler()
    fmt = RuntimeFormatter(start_time,
                           '%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
    file_handler.setFormatter(fmt)
    console_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    # root.addHandler(console_handler)
    root.setLevel(logging.DEBUG)


def log_listener_process(queue, logfile, start_time):
    configure_listener(logfile, start_time)
    while True:
        while not queue.empty():
            record = queue.get()

            if record == "END":
                return

            logger = logging.getLogger(record.name)
            logger.handle(record)