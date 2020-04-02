import os
import re
import json
import sys
import subprocess
import shlex


def run_command(command):
    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
    rc = process.poll()
    return rc


def eman2_main(root, name, eman2_args, run_automatically=False):
    """

    1. Make EMAN2 dir
    2. Copy over template scripts
    3. If run automatically, run scripts up to end point

    Returns:

    """

    # Set up an EMAN2 directory
    processed_data_dir = root + "/processed_data"
    e2_dir = processed_data_dir + "/EMAN2"
    if not os.path.exists(e2_dir):
        os.mkdir(e2_dir)

    current_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    template = current_dir + "../../templates/eman2/eman2_process.py"
    template_path = os.path.realpath(template)
    print(template_path)
    new_script = "%s/eman2_process.py" % e2_dir

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

    # Run automatically if desired
    if run_automatically:
        command = "python3 %s" % new_script
        run_command(command)
