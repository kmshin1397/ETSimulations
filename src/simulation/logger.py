import logging
from logging import handlers
from datetime import timedelta
import os


class RuntimeFormatter(logging.Formatter):

    def __init__(self, start_time, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = start_time

    def formatTime(self, record, datefmt=None):
        elapsed_seconds = record.created - self.start_time
        # Using timedelta here for convenient default formatting
        elapsed = timedelta(seconds = elapsed_seconds)
        return "{}".format(elapsed)


def truncate_utf8_chars(filename, count, ignore_newlines=True):
    """
    Truncates last `count` characters of a text file encoded in UTF-8/ASCII.

    Args:
        filename: The path to the text file to read
        count: Number of UTF-8 characters to remove from the end of the file
        ignore_newlines: Set to true, if the newline character at the end of the file should be
            ignored
    """
    with open(filename, 'rb+') as f:
        last_char = None

        size = os.fstat(f.fileno()).st_size

        offset = 1
        chars = 0
        while offset <= size:
            f.seek(-offset, os.SEEK_END)
            b = ord(f.read(1))

            if ignore_newlines:
                if b == 0x0D or b == 0x0A:
                    offset += 1
                    continue

            if b & 0b10000000 == 0 or b & 0b11000000 == 0b11000000:
                # This is the first byte of a UTF8 character
                chars += 1
                if chars == count:
                    # When `count` number of characters have been found, move current position back
                    # with one byte (to include the byte just checked) and truncate the file
                    f.seek(-1, os.SEEK_CUR)
                    f.truncate()
                    return
            offset += 1


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


def metadata_log_listener_process(queue, logfile):
    with open(logfile, "w") as f:
        f.write("[")

    while True:
        while not queue.empty():
            record = queue.get()

            if record.startswith("END"):
                truncate_utf8_chars(logfile, 1, ignore_newlines=True)
                with open(logfile, "a") as f:
                    f.write("]\n")
                return
            else:
                with open(logfile, "a") as f:
                    f.write(record + ",\n")
