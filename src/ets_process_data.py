# Built-in modules
import time
import os
import multiprocessing
from shutil import rmtree, copyfile
import argparse
import json
import requests
import logging
from logging import handlers
import signal
import warnings

# External modules
import numpy as np
import yaml

# Custom modules
from .simulation.notify import send_email
from .simulation.logger import log_listener_process


def parse_inputs():
    """ Instantiate and set up the command line arguments parser for the ets_process_data module

    Returns: None

    """
    parser = argparse.ArgumentParser(
        description='Process simulated tilt stacks generated with ets_process_data.py')
    parser.add_argument('-i', '--input', required=True,
                        help='the input configurations YAML file')
    arguments = parser.parse_args()
    input_file = arguments.input
    stream = open(input_file, 'r')
    return yaml.load(stream)


def configure_root_logger(queue):
    """ Helper function to initialize and configure the main logger instance to handle log messages.

    Args:
        queue: An instance of the  multiprocessing.queue class which provides thread-safe handling
            of log messages coming from many child processes.

    Returns: None

    """
    h = handlers.QueueHandler(queue)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.INFO)


def main():
    pass


if __name__ == '__main__':
    start_time = time.time()
    logger = logging.getLogger(__name__)

    args = parse_inputs()
    if "name" not in args:
        args["name"] = os.path.basename(args["root"])

    if args["model"].endswith(".pdb") and "apix" not in args:
        print("An apix value must be provided with a PDB model!")
        exit(1)

    send_notification = False
    if "email" in args:
        send_notification = True

    metadata_queue = multiprocessing.Queue()

    # Start the logger process
    logs_queue = multiprocessing.Queue()
    logfile = "%s/%s.log" % (args["root"], args["name"])
    log_listener = multiprocessing.Process(target=log_listener_process, args=(logs_queue, logfile,
                                                                              start_time))
    log_listener.start()

    configure_root_logger(logs_queue)

    main()
    logs_queue.put("END")
    log_listener.join()
