""" This module is the entry point for processing simulated raw tilt stacks generated by
    ets_generate_data.py.

Specifically, given a list of parameters in a configuration YAML file, project directories will be
set up for specified cryo-ET processing softwares, i.e. EMAN2, and scripts generated to run all
specified steps of the data processing process.

"""
# Built-in modules
import os
import argparse

# External modules
import yaml

# Custom modules
from processors.eman2_processor import eman2_main
from processors.imod_processor import imod_main
from processors.i3_processor import i3_main

# This table maps the names of the various processors (cryo-ET softwares) to the functions which
# implement the set-up logic for that software.
processor_handlers = {"eman2": eman2_main, "imod": imod_main, "i3": i3_main}


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
    return yaml.load(stream, Loader=yaml.FullLoader)


def main(args):
    """ Create the processed_data directory if needed and call the proper handlers for all specified
    processors parsed from the configurations

    Args:
        args: The parsed dictionary of input parameters from the configuration file.

    Returns: None

    """

    # Set up processed data directories
    # Trailing slash not expected by rest of program
    args["root"] = args["root"].rstrip("/")
    processed_data_dir = args["root"] + "/processed_data"
    if not os.path.exists(processed_data_dir):
        os.mkdir(processed_data_dir)

    # Read processor requests
    for processor in args["processors"]:
        print("################################\n")
        print("Working on processor %s" % processor["name"])
        processor_handler = processor_handlers[processor["name"]]
        processor_handler(args["root"], args["name"], processor["args"])
        print("")


if __name__ == '__main__':
    configs = parse_inputs()
    if "name" not in configs:
        configs["name"] = os.path.basename(configs["root"])

    main(configs)
