# Built-in modules
import time
import os
import argparse

# External modules
import yaml

# Custom modules
from processors.eman2_processor import eman2_main

# Set up processor handlers table
processor_handlers = {"eman2": eman2_main}


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


def main(args):

    # Set up processed data directories
    # Trailing slash not expected by rest of program
    args["root"] = args["root"].rstrip("/")
    processed_data_dir = args["root"] + "/processed_data"
    if not os.path.exists(processed_data_dir):
        os.mkdir(processed_data_dir)

    # Read processor requests
    for processor in args["processors"]:
        print("Working on processor %s" % processor["name"])
        processor_handler = processor_handlers[processor["name"]]
        processor_handler(args["root"], args["name"], processor["args"],
                          run_automatically=processor["run_automatically"])

    pass


if __name__ == '__main__':
    start_time = time.time()

    configs = parse_inputs()
    if "name" not in configs:
        configs["name"] = os.path.basename(configs["root"])

    send_notification = False
    if "email" in configs:
        send_notification = True

    main(configs)
