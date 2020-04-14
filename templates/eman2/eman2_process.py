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
steps_to_run = []

# Particle picking parameters
particle_coordinates_parameters = {}

e2import_parameters = {}

e2tomogram_parameters = {}

e2spt_tomoctf_parameters = {}

e2spt_extract_parameters = {}

e2spt_buildsets_parameters = {}

e2spt_sgd_parameters = {}

e2spt_refine_parameters = {}


# ==========================================================

def run_process_with_params(base_command, params_dict, get_command_without_running=False):
    """ Helper function to run a given command line command, used to invoke various EMAN2 programs.
    Command line arguments to the base command can be passed in as a dictionary of key, value pairs.
    Arguments that do not have a value (i.e --help for many programs) should instead be passed in
    with the special value of 'enabled' for that key.

    Args:
        base_command: The base command to run, i.e. e2tomogram.py
        params_dict: A dictionary of input arguments to the command
        get_command_without_running: Option to return the assembled full command without actually
            running it
    """
    for arg, value in params_dict.items():
        if value == "enable":
            base_command += " --%s" % arg
        else:
            base_command += " --%s=%s" % (arg, str(value))

    if get_command_without_running:
        return base_command
    else:
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
def import_tiltseries(get_command_without_running=False):
    """ Run the e2import.py program to import tilt stacks """
    results = ""
    # Scan everything in the raw data folder
    for dir_entry in os.scandir(raw_data_dir):
        # For every directory found which begins with the proper project name, i.e. assumed to
        # contain a raw stack
        if dir_entry.is_dir() and dir_entry.name.startswith(name):
            stack_basename = dir_entry.name
            stack_to_import = dir_entry.path + "/%s.mrc" % stack_basename
            base_command = "e2import.py %s" % stack_to_import
            result = run_process_with_params(base_command, e2import_parameters,
                                             get_command_without_running)

            if not get_command_without_running and result != 0:
                print("Error with import tiltseries, exiting...")
                exit(1)
            else:
                # If we're returning the commands, append with newline
                if get_command_without_running:
                    results += result + "\n"
                # Otherwise, we check for errors
                else:
                    if result != 0:
                        results = result
                    else:
                        results = 0

    return results


def reconstruct_tomograms(get_command_without_running=False):
    """ Run the e2tomogram.py program to reconstruct tomograms """

    # If we haven't imported stacks yet, we don't know the exact reconstruction command
    if get_command_without_running and not os.path.exists(os.path.join(eman2_root, "tiltseries")):
        command = "e2tomogram.py tiltseries/{some_tiltseries_not_imported_yet}.hdf"
        result = run_process_with_params(command, e2tomogram_parameters,
                                         get_command_without_running)
        return result
    else:
        results = ""
        # Iterate through each tiltseries
        for tiltseries in os.scandir(os.path.join(eman2_root, "tiltseries")):
            command = "e2tomogram.py %s" % ("tiltseries/" + tiltseries.name)
            result = run_process_with_params(command, e2tomogram_parameters,
                                             get_command_without_running)
            if not get_command_without_running and result != 0:
                print("Error with reconstructing tomograms, exiting...")
                exit(1)
            else:
                # If we're returning the commands, append with newline
                if get_command_without_running:
                    results += result + "\n"
                # Otherwise, we check for errors
                else:
                    if result != 0:
                        results = result
                    else:
                        results = 0

        return results


def estimate_ctf(get_command_without_running=False):
    """ Run the e2spt_tomoctf.py program to estimate CTF for the tomograms """
    command = "e2spt_tomoctf.py"
    result = run_process_with_params(command, e2spt_tomoctf_parameters, get_command_without_running)
    if not get_command_without_running and result != 0:
        print("Error with estimating CTF values, exiting...")
        exit(1)
    else:
        return result


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


def extract_particles(get_command_without_running=False):
    """ Run the e2spt_extract.py program to extract subvolumes after writing out the particle
        coordinates to the EMAN2 info files
    """
    # Record particles
    if not get_command_without_running:
        mode = ""
        if "mode" in particle_coordinates_parameters:
            mode = particle_coordinates_parameters["mode"]
        else:
            print("Error - Missing 'mode' parameter in particle_coordinates_parameters")
            exit(1)

        coordinates_file = ""
        if "coordinates_file" in particle_coordinates_parameters:
            coordinates_file = particle_coordinates_parameters["coordinates_file"]
        else:
            print("Error - Missing 'coordinates_file' parameter in particle_coordinates_parameters")
            exit(1)

        unbinned_boxsize = 64
        if "unbinned_boxsize" in particle_coordinates_parameters:
            unbinned_boxsize = particle_coordinates_parameters["unbinned_boxsize"]

        if mode == "single":
            info_files = eman2_root + "/info"
            for f in os.listdir(info_files):
                info_file = os.fsdecode(f)
                if info_file.startswith(name):
                    record_eman2_particle(coordinates_file, info_files + "/" + info_file, name,
                                          unbinned_boxsize)
        elif mode == "multiple":
            for subdir in os.scandir(raw_data_dir):
                base_name = subdir.name
                if base_name.startswith(name):
                    coordinates = os.path.join(subdir.path, coordinates_file)
                    info_file = os.path.join(eman2_root, "info", "%s_info.json" % base_name)
                    record_eman2_particle(coordinates, info_file, name, unbinned_boxsize)

        else:
            print("Error - Invalid 'mode' for particle coordinates. Should be 'single' or "
                  "'multiple'")
            exit(1)

    # Extract particles
    base_command = "e2spt_extract.py --label=%s" % name
    result = run_process_with_params(base_command, e2spt_extract_parameters,
                                     get_command_without_running)
    if not get_command_without_running and result != 0:
        print("Error with extracting particles, exiting...")
        exit(1)
    else:
        return result


def make_particle_set(get_command_without_running=False):
    """ Run the e2spt_buildsets.py program to create a list of particles for averaging """
    # Build set
    base_command = "e2spt_buildsets.py --label=%s" % name
    result = run_process_with_params(base_command, e2spt_buildsets_parameters,
                                     get_command_without_running)
    if not get_command_without_running and result != 0:
        print("Error with building the particle set, exiting...")
        exit(1)
    else:
        return result


def make_initial_model(get_command_without_running=False):
    """ Run the e2spt_sgd program to automatically generate an initial reference for averaging """
    base_command = "e2spt_sgd.py sets/%s.lst" % name
    result = run_process_with_params(base_command, e2spt_sgd_parameters,
                                     get_command_without_running)
    if not get_command_without_running and result != 0:
        print("Error with generating the initial model, exiting...")
        exit(1)
    else:
        return result


def run_refinement(get_command_without_running=False):
    """ Run the e2spt_refine.py program to do sub-tomogram refinement """
    particle_set_file = "sets/%s.lst" % name
    reference_file = "sptsgd_00/output.hdf"
    base_command = "e2spt_refine.py %s --reference=%s" % (particle_set_file, reference_file)
    result = run_process_with_params(base_command, e2spt_refine_parameters,
                                     get_command_without_running)
    if not get_command_without_running and result != 0:
        print("Error with the 3D refinement, exiting...")
        exit(1)
    else:
        return result


# ==========================================================


# ==================== Main process ====================

# This table maps the keyword for each processing step to the functions that implement the actions
# for them.
functions_table = {
    "import": import_tiltseries,
    "reconstruct": reconstruct_tomograms,
    "estimate_ctf": estimate_ctf,
    "extract": extract_particles,
    "build_set": make_particle_set,
    "generate_initial_model": make_initial_model,
    "3d_refinement": run_refinement
}


def collect_and_output_commands(output_file):
    commands = []
    for step in functions_table:
        function = functions_table[step]
        command = function(get_command_without_running=True)
        command += "\n"
        commands.append(command)

    with open(output_file, 'w') as f:
        f.writelines(commands)


def main():
    # To start, go into EMAN2 project directory
    os.chdir(eman2_root)

    for step in steps_to_run:
        print("=============================================")
        print("Running step: %s" % step)
        if step in functions_table:
            function = functions_table[step]
            function()
        else:
            print("ERROR: %s is not a valid EMAN2 processing step to run" % step)
            exit(1)


if __name__ == '__main__':
    main()
