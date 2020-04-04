"""
This script runs a series of EMAN2 processing steps in the order specified in the steps_to_run
variable. The steps_to_run and other parameters for various steps will be filled in dynamically by
the eman2_processor.py module based on the configurations file provided to ets_process_data.py by
the user.

Note: Python3 is required to run this script.

"""
import os
import subprocess
import shlex
import numpy as np
import json

# ==================== Input parameters ====================
# General parameters
eman2_root = ""
raw_data_dir = ""
name = ""
particle_coordinates_file = ""
steps_to_run = []

# Importation parameters
e2import_parameters = {}

# Reconstruction parameters
e2tomogram_parameters = {}

e2spt_extract_parameters = {}

e2spt_buildsets_parameters = {}

e2spt_sgd_parameters = {}

e2spt_refine_parameters = {}


# ==========================================================

def run_process_with_params(base_command, params_dict):
    """ Helper function to run a given command line command, used to invoke various EMAN2 programs.
    Command line arguments to the base command can be passed in as a dictionary of key, value pairs.
    Arguments that do not have a value (i.e --help for many programs) should instead be passed in
    with the special value of 'enabled' for that key.

    Args:
        base_command: The base command to run, i.e. e2tomogram.py
        params_dict: A dictionary of input arguments to the command

    Returns: The return code of the process

    """
    for arg, value in params_dict.items():
        if value == "enable":
            base_command += " --%s" % arg
        else:
            base_command += " --%s=%s" % (arg, str(value))

    print("Running command: ")
    print(base_command)

    process = subprocess.Popen(shlex.split(base_command), stdout=subprocess.PIPE)
    while True:
        output = os.fsdecode(process.stdout.readline())
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
    rc = process.poll()
    return rc


# ==================== Processing steps ====================
def import_tiltseries():
    """ Run the e2import.py program to import tilt stacks """
    # Scan everything in the raw data folder
    for dir_entry in os.scandir(raw_data_dir):
        # For every directory found which begins with the proper project name, i.e. assumed to
        # contain a raw stack
        if dir_entry.is_dir() and dir_entry.name.startswith(name):
            stack_basename = dir_entry.name
            stack_to_import = dir_entry.path + "/%s.mrc" % stack_basename
            base_command = "e2import.py %s" % stack_to_import
            run_process_with_params(base_command, e2import_parameters)


def reconstruct_tomograms():
    """ Run the e2tomogram.py program to reconstruct tomograms """
    # Iterate through each tiltseries
    for tiltseries in os.scandir(os.path.join(eman2_root, "tiltseries")):
        command = "e2tomogram.py %s" % ("tiltseries/" + tiltseries.name)
        run_process_with_params(command, e2tomogram_parameters)


def record_eman2_particle(particles_file, info_file, particle_name, boxsize):
    """ Write out particle coordinates to a EMAN2 tomogram info JSON file

    Args:
        particles_file: The text file containing the converted particle coordinates
        info_file: The JSON file in the info directory of the EMAN2 project folder
            corresponding to the tomogram in question
        particle_name: The name to assign to the particle within the EMAN2 project
        boxsize: The EMAN2 box size (as seen in the EMAN2 box picker) to use for the particles.

    Returns: None

    """
    particles = np.loadtxt(particles_file)

    # If there was only one model point
    if particles.ndim == 1:
        # Wrap in a new list to make it two-dimensional so next for loop will work
        particles = [particles]

    with open(info_file, 'r') as f:
        tomogram_info = json.load(f)

        # Build up boxes
        boxes = []
        for particle in particles:
            x, y, z = particle[0], particle[1], particle[2]

            box = [x, y, z]

            box.extend(["manual", 0.0, 0])
            boxes.append(box)

        tomogram_info["boxes_3d"] = boxes

        tomogram_info["class_list"] = {"0": {"boxsize": boxsize, "name": particle_name}}

    with open(info_file, 'w') as f:
        json.dump(tomogram_info, f, indent=4)


def make_particle_set():
    """ Run the e2spt_extract.py and e2spt_buildsets.py programs to extract subvolumes and create a
        list of them for averaging.
    """
    # Record particles
    info_files = eman2_root + "/info"
    for f in os.listdir(info_files):
        info_file = os.fsdecode(f)
        if info_file.startswith(name):
            record_eman2_particle(particle_coordinates_file, info_files + "/" + info_file, name,
                                  128)

    # Extract particles
    base_command = "e2spt_extract.py --label=%s" % name
    run_process_with_params(base_command, e2spt_extract_parameters)

    # Build set
    base_command = "e2spt_buildsets.py --label=%s" % name
    run_process_with_params(base_command, e2spt_buildsets_parameters)


def make_initial_model():
    """ Run the e2spt_sgd program to automatically generate an initial reference for averaging """
    base_command = "e2spt_sgd sets/%s.lst" % name
    run_process_with_params(base_command, e2spt_sgd_parameters)


def run_sta():
    """ Run the e2spt_refine.py program to do sub-tomogram averaging """
    particle_set_file = "sets/%s.lst" % name
    reference_file = "sptsgd_00/output.hdf"
    base_command = "e2spt_refine.py %s --reference=%s" % (particle_set_file, reference_file)
    run_process_with_params(base_command, e2spt_refine_parameters)


# ==========================================================


# ==================== Main process ====================

# This table maps the keyword for each processing step to the functions that implement the actions
# for them.
functions_table = {
    "import": import_tiltseries,
    "reconstruct": reconstruct_tomograms,
    "extract": make_particle_set,
    "initial_model": make_initial_model,
    "average": run_sta
}


def main():
    # To start, go into EMAN2 project directory
    os.chdir(eman2_root)

    for step in steps_to_run:
        print("=============================================")
        print("Running step: %s" % step)
        function = functions_table[step]
        function()


if __name__ == '__main__':
    main()
