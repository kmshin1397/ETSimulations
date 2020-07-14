import numpy as np
import os
import sys
import re


def imod_real_setup_sta(artia_args):
    """
    Write out the files necessary to run the MATLAB import script for reconstructions in Artiatomi
    Args:
        artia_args: The processor arguments

    Returns: Tuple of motive lists file and tomogram numbers file

    """

    imod_project_dir = artia_args["imod_dir"]
    look_for_dirs_starting_with = artia_args["dirs_start_with"]
    artia_root = artia_args["artia_dir"]
    initMOTLs = []
    tomonumbers = []
    for folder in os.listdir(os.fsencode(imod_project_dir)):
        base = os.path.splitext(os.fsdecode(folder))[0]
        if base.startswith(look_for_dirs_starting_with):
            motl_name = ""
            for file in os.listdir(os.fsencode(imod_project_dir + "/%s" % base)):
                if os.fsdecode(file).endswith("_motl.em"):
                    motl_name = os.path.basename(os.fsdecode(file))

            motl = imod_project_dir + "/%s/%s" % (base, motl_name)
            tomo_num = int(base.split("_")[-1]) + 1

            initMOTLs.append(motl)
            tomonumbers.append(tomo_num)

    motl_out = os.path.join(artia_root, "motls.txt")
    tomonums_out = os.path.join(artia_root, "tomonums.txt")

    with open(motl_out, 'w') as f:
        f.write(' '.join(map(str, initMOTLs)))

    with open(tomonums_out, 'w') as f:
        f.write(' '.join(map(str, tomonumbers)))

    return motl_out, tomonums_out


def imod_processor_setup_sta(root, name, artia_args):
    pass


def setup_reconstructions_script(root, name, artia_args):

    if artia_args["real_data_mode"]:
        artia_root = artia_args["artia_dir"]
        imod_root = artia_args["imod_dir"]
        dir_starts_with = artia_args["dir_starts_with"]
    else:
        artia_root = os.path.join(root, "processed_data", "Artiatomi")
        imod_root = os.path.join(root, "processed_data", "IMOD")
        dir_starts_with = name

    # Use template file to create Matlab script to run the remaining steps
    current_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    template = current_dir + "../../templates/artiatomi/setup_artia_reconstructions.m"
    template_path = os.path.realpath(template)
    new_script = os.path.join(artia_root, "setup_artia_reconstructions.m")
    print("")
    print("Creating processing script at: %s" % new_script)

    with open(new_script, "w") as new_file:
        with open(template_path, "r") as base_file:
            # First look for the input params section
            while True:
                line = base_file.readline()
                if re.match(r"^%% Input parameters", line):
                    break
                else:
                    new_file.write(line)

            # Now start replacing input params
            while True:
                line = base_file.readline()
                # Break once we reach the end of the segment
                if re.match(r"^%% Process", line):
                    break

                # If we are at an assignment line
                elif re.match(r".+ =", line):
                    line = line.strip()
                    tokens = line.split(" ")
                    variable_name = tokens[0]

                    value_to_write_out = ""
                    if variable_name == "project_root":
                        value_to_write_out = f"\'{imod_root}\';"
                    elif variable_name == "dir_starts_with":
                        value_to_write_out = f"\'{dir_starts_with}\';"
                    elif variable_name == "template_config":
                        value_to_write_out = f"\'{artia_args['template_config']}\';"
                    elif variable_name == "particles_dir":
                        value_to_write_out = "\'particles\';"
                    else:
                        print("Missing Dynamo processing parameter: %s!" % variable_name)
                        exit(1)

                    new_line = " ".join([variable_name, "=", value_to_write_out, "\n"])

                    new_file.write(new_line)

                # Other lines in the segment - probably just comments
                else:
                    new_file.write(line)

            # For the rest of the code, just write it out
            while True:
                line = base_file.readline()
                if len(line) == 0:
                    break
                else:
                    new_file.write(line)


def artiatomi_main(root, name, artia_args):
    if artia_args["source_type"] == "imod":
        if artia_args["real_data_mode"]:
            imod_real_setup_reconstructions(artia_args)
        else:
            imod_processor_setup_reconstructions(root, name, artia_args)
    elif artia_args["source_type"] == "eman2":
        if artia_args["real_data_mode"]:
            eman2_real_to_i3(i3_args)
        else:
            eman2_processor_to_i3(root, name, i3_args)
    else:
        print("Error: Invalid I3 'source_type")
        exit(1)