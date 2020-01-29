import re
from tempfile import mkstemp
import os
from shutil import move
import sys
from subprocess import check_output
import numpy as np
import random


def load_tbl_file_orientations(filename):
    raw_data = np.loadtxt(filename)
    orientations = raw_data[:, 6:9]
    return orientations


def get_random_tbl_orientation(loaded_orientations):
    # global loaded_orientations
    # return loaded_orientations.pop(0)
    choice = random.choice(loaded_orientations).tolist()
    return [-choice[2], -choice[1], -choice[0]]
    # return [choice[0] + 360, choice[1] + 360, choice[2] + 360]


# Replace line in file with a new line
def replace(file_path, pattern, subst):
    # Create temp file
    fh, abs_path = mkstemp()
    with os.fdopen(fh, 'w') as new_file:
        with open(file_path) as old_file:
            for line in old_file:
                new_line = re.sub(pattern, subst, line)
                new_file.write(new_line)

    # Remove original file
    os.remove(file_path)
    # Move new file
    move(abs_path, file_path)


# Only rewrite T4SS map source, not gold beads
def replace_particle(file_path, pattern, subst):
    # Create temp file
    fh, abs_path = mkstemp()
    found_T4SS = False
    with os.fdopen(fh, 'w') as new_file:
        with open(file_path) as old_file:
            for line in old_file:
                if not found_T4SS:
                    new_line = re.sub(pattern, subst, line)
                    new_file.write(new_line)
                    if re.match(pattern, line) is not None:
                        found_T4SS = True
                else:
                    new_file.write(line)

    # Remove original file
    os.remove(file_path)
    # Move new file
    move(abs_path, file_path)


def replace_nonoise(file_path, pattern, subst):
    # Create temp file
    fh, abs_path = mkstemp()
    found_first = False
    with os.fdopen(fh, 'w') as new_file:
        with open(file_path) as old_file:
            for line in old_file:
                if found_first:
                    new_line = re.sub(pattern, subst, line)
                    new_file.write(new_line)
                else:
                    if re.match(pattern, line) is not None:
                        found_first = True
                    new_file.write(line)

    # Remove original file
    os.remove(file_path)
    # Move new file
    move(abs_path, file_path)


# Enters the simulation configurations file and adds in a new set of
# random orientations, returning the random orientations used.
def replace_orientations(file_path, orientations):
    random_orientations = []

    pattern = r"^[-+]?[0-9]+(\s+[-+]?[0-9]+){5}"
    # Create temp file
    fh, abs_path = mkstemp()
    with os.fdopen(fh, 'w') as new_file:
        with open(file_path) as old_file:
            for line in old_file:
                new_orientation = line
                if re.match(pattern, line) is not None:
                    split = line.split(' ')
                    coord = (split[0], split[1], split[2])

                    # rand = get_random_orientation()
                    rand = get_random_tbl_orientation(orientations)

                    new_orientation = "%s %s %s %d %d %d" % (coord[0],
                                                             coord[1], coord[2], rand[0], rand[1],
                                                             rand[2])
                    random_orientations.append(rand)

                new_line = re.sub(pattern, new_orientation, line)
                new_file.write(new_line)

    # Remove original file
    os.remove(file_path)
    # Move new file
    move(abs_path, file_path)

    return random_orientations


def modify_sim_input_files(simulation, orientations):
    image_file_out_pattern = "^image_file_out = .*\n"
    replacement_line = "image_file_out = %s\n" % simulation.tiltseries_file
    replace(simulation.sim_input_file, image_file_out_pattern, replacement_line)

    replacement_line = "image_file_out = %s\n" % simulation.nonoise_tilts_file
    replace_nonoise(simulation.sim_input_file, image_file_out_pattern, replacement_line)

    coord_file_pattern = "^coord_file_in = .*\n"
    new_coord_file = "coord_file_in = %s\n" % simulation.coordinates_file
    replace(simulation.sim_input_file, coord_file_pattern, new_coord_file)

    map_file_pattern = "^map_file_re_in = .*\n"
    new_file_in = "map_file_re_in = %s\n" % simulation.particle_map_file
    replace_particle(simulation.sim_input_file, map_file_pattern, new_file_in)

    # orientation_pattern = r"^[-+]?[0-9]+(\s+[-+]?[0-9]+){5}"
    # new_orientation = "0 0 0 %d %d %d"%simulation.orientation
    random_orientations = replace_orientations(simulation.coordinates_file, orientations)

    return random_orientations


def run_tem_simulator(simulation):
    print("Running TEM Simulator...")
    # log(simulation.log_file, "Running TEM Simulator...")
    TEM_exec_path = '/home/kshin/Documents/software/TEM-simulator_1.3/src/TEM-simulator'
    command = TEM_exec_path + ' ' + simulation.sim_input_file
    # log(simulation.log_file, check_output(command.split()).decode(sys.stdout.encoding))
    check_output(command.split()).decode(sys.stdout.encoding)
