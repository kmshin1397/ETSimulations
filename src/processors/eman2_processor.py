""" This module implements the processing function for the EMAN2 software package.

The module will create an EMAN2 project directory and set up a new Python script to process the
raw data from ets_generate_data.py through the EMAN2 tomography pipeline.
"""

import os
import re
import json
import sys
import importlib.util
from shutil import rmtree


def validate_steps_to_run(steps_to_run):
    valid_steps = ["import",
                   "reconstruct",
                   "estimate_ctf",
                   "extract",
                   "build_set",
                   "generate_initial_model",
                   "3d_refinement"]
    for step in steps_to_run:
        if step not in valid_steps:
            print("ERROR: %s is not a valid EMAN2 processing step to run" % step)
            exit(1)


def eman2_main(root, name, eman2_args):
    """ The method to set-up tiltseries processing using EMAN2

    The steps taken are:
    1. Make EMAN2 dir
    2. Copy over template script
    3. Fill in the specific parameters for the scripts based on the passed in arguments

    Returns: None

    """

    validate_steps_to_run(eman2_args["steps_to_run"])

    # Set up an EMAN2 directory
    processed_data_dir = root + "/processed_data"
    e2_dir = processed_data_dir + "/EMAN2"
    if not os.path.exists(e2_dir):
        os.mkdir(e2_dir)

    current_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    template = current_dir + "../../templates/eman2/eman2_process.py"
    template_path = os.path.realpath(template)
    new_script = "%s/eman2_process.py" % e2_dir
    print("")
    print("Creating processing script at: %s" % new_script)

    with open(new_script, "w") as new_file:
        with open(template_path, "r") as base_file:
            # First look for the input params section
            while True:
                line = base_file.readline()
                if re.match(r"^# =+ Input parameters", line):
                    break
                else:
                    new_file.write(line)

            # Now start replacing input params
            while True:
                line = base_file.readline()
                # Break once we reach the end of the segment
                if re.match(r"^# =+", line):
                    break

                # If we are at an assignment line
                elif re.match(r".+ =", line):
                    line = line.strip()
                    tokens = line.split(" ")
                    variable_name = tokens[0]

                    value_to_write_out = ""
                    if variable_name == "raw_data_dir":
                        value_to_write_out = "\"%s\"" % (root + "/raw_data")
                    elif variable_name == "eman2_root":
                        value_to_write_out = "\"%s\"" % e2_dir
                    elif variable_name == "name":
                        value_to_write_out = "\"%s\"" % name
                    elif variable_name in eman2_args:
                        value_to_write_out = json.dumps(eman2_args[variable_name], indent=2)
                    else:
                        print("Missing EMAN2 processing parameter: %s!" % variable_name)
                        exit(1)

                    new_line = " ".join([variable_name, "=", value_to_write_out, "\n"])

                    new_file.write(new_line)

                # Other lines - probably just comments
                else:
                    new_file.write(line)

            # For the rest of the code, just write it out
            while True:
                line = base_file.readline()
                if len(line) == 0:
                    break
                else:
                    new_file.write(line)

    # Also output the commands as a simple text file for easier viewing and modification if desired
    spec = importlib.util.spec_from_file_location("eman2_process", new_script)
    eman2_process_script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eman2_process_script)
    text_output = "%s/eman2_process_commands.txt" % e2_dir
    print("")
    print("If desired, the full set of EMAN2 commands that have been assembled and available in "
          "the newly generated eman2_process.py script can be found in raw text form at: %s" %
          text_output)
    eman2_process_script.collect_and_output_commands(text_output)

    # Clean up compiled pycache from loading the script
    rmtree(e2_dir + "/__pycache__")
