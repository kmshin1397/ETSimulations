import numpy as np
import os
import sys
import re
import json
from scipy.spatial.transform import Rotation as R
import shutil
import struct


#################################
#   General Helper Functions    #
#################################

def rotate_positions_around_z(positions):
    """
    Given a list of coordinates, rotate them all by 90 degrees around the z-axis. This is used to
        convert particle coordinates from the raw tiltseries to the final reconstruction's
        coordinate system for simulated data.

    Args:
        positions: A list of [x, y, z] coordinates

    Returns: None

    """
    rot = R.from_euler('zxz', (90, 0, 0), degrees=True)
    for i, point in enumerate(positions):
        positions[i] = np.dot(rot.as_matrix(), np.array(point))

    return positions


def convert_slicer_to_motl(orientations):
    """
    Convert a set of Slicer angles to the reference-to-particle ZXZ, external Euler angles for Artiatomi
    Args:
        orientations: The list of Slicer angles

    Returns: The list of Euler angles

    """
    for i, point in enumerate(orientations):
        slicer = orientations[i]
        rot = R.from_euler("zyx", [slicer[2], slicer[1], slicer[0]], degrees=True)
        ref_to_part = rot.inv()
        eulers = ref_to_part.as_euler("zxz", degrees=True)
        orientations[i] = eulers

    return orientations


def get_slicer_info(mod_file):
    """
    Open an IMOD .mod file and retrieve the Slicer information

    Args:
        mod_file: The .mod file path

    Returns: A list of Slicer point objects with keys {"angles", "coords"}

    """
    results = []
    with open(mod_file, "rb") as file:
        token = file.read(4)
        if token != b'IMOD':
            print("ID of .mod file is not 'IMOD'. This does not seem to be an IMOD MOD file!")
            exit(1)

        # Read past rest of ID and file header
        file.read(236)

        while token != b'IEOF':
            file.seek(-3, 1)
            token = file.read(4)
            if token == b'SLAN':
                # Read past SLAN object size and time
                file.read(8)

                angles = struct.unpack('>' + ('f' * 3), file.read(4 * 3))
                xyz = struct.unpack('>' + ('f' * 3), file.read(4 * 3))

                results.append({"angles": angles, "coords": xyz})
                file.read(32)

                # Read forward a little so next iteration of while loop starts at end of SLAN object
                file.read(3)
            elif token == b'OBJT':
                # Objects are 176 bytes; skip path to make reading faster
                file.read(176)
                # Read forward a little so next iteration of while loop starts at end of object
                file.read(3)

    if len(results) == 0:
        print("Reached end of MOD file without finding slicer angles!")
        exit(1)

    return results

#######################
#   IMOD Functions    #
#######################

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


def write_out_motl_files_simulated(root, name, xyz_name, motl_name):
    """
    Iterate through an IMOD Processor project and set up text files for Artiatomi to read in for its marker files

    Args:
        root: The ETSimulations project root
        name: The project/particle name
        xyz_name: The file name to give each XYZ coordinates file
        motl_name: The file name to give each Euler angles file

    Returns: None
    """
    metadata_file = os.path.join(root, "sim_metadata.json")

    with open(metadata_file, "r") as f:
        metadata = json.loads(f.read())

        # -------------------------------------
        # Retrieve parameters to write to files
        # -------------------------------------
        for num, tomogram in enumerate(metadata):
            basename = "%s_%d" % (name, tomogram["global_stack_no"])
            tomogram_dir = os.path.join(root, "processed_data/IMOD", basename)

            artia_dir = os.path.join(root, "processed_data/Artiatomi", basename)

            # Positions for TEM-Simulator are in nm, need to convert to pixels
            positions = np.array(tomogram["positions"]) / tomogram["apix"]
            # During reconstruction, there is a 90 degree rotation around the z-axis, so correct for
            # that with the positions
            positions = rotate_positions_around_z(positions)

            slicer_angles_csv = os.path.join(tomogram_dir, "%s_slicerAngles.csv" % name)
            orientations = np.loadtxt(slicer_angles_csv, delimiter=",")
            eulers = convert_slicer_to_motl(orientations)
            # Compile Slicer infos
            slicer_info = []
            for i, coords in enumerate(positions):
                angles = eulers[i]
                slicer_info.append({"coords": coords, "angles": angles})

            # Write out MOTL files for each tomogram
            xyz_motl = os.path.join(artia_dir, xyz_name)
            eulers_motl = os.path.join(artia_dir, motl_name)
            xyz_motl_file = open(xyz_motl, "w")
            eulers_motl_file = open(eulers_motl, "w")
            for info in slicer_info:
                coords = info["coords"]
                angles = info["angles"]
                xyz_line = "{:f} {:f} {:f}\n".format(coords[0], coords[1], coords[2])
                xyz_motl_file.write(xyz_line)
                motl_line = "{:f} {:f} {:f}\n".format(angles[0], angles[1], angles[2])
                eulers_motl_file.write(motl_line)

            xyz_motl_file.close()
            eulers_motl_file.close()


def write_out_motl_files_real(artia_root, xyz_name, motl_name):
    """
    Iterate through Artiatomi files copied over from IMOD real data and set up text files for Artiatomi to read in for
        its marker files based on slicer .mod files

    Args:
        artia_root: The Artiatomi project root
        xyz_name: The file name to give each XYZ coordinates file
        motl_name: The file name to give each Euler angles file

    Returns: None
    """
    for subdir in os.listdir(artia_root):
        # Find the mod file
        mod_file = ""
        for file in os.listdir(os.path.join(artia_root, subdir)):
            if file.endswith(".mod"):
                mod_file = os.path.join(artia_root, subdir, file)
                break

        if mod_file == "":
            print("ERROR: No mod was found for sub-directory: %s" % subdir)
            exit(1)

        slicer_info = get_slicer_info(mod_file)

        # Write out MOTL files for each tomogram
        xyz_motl = os.path.join(artia_root, subdir, xyz_name)
        eulers_motl = os.path.join(artia_root, subdir, motl_name)
        xyz_motl_file = open(xyz_motl, "w")
        eulers_motl_file = open(eulers_motl, "w")
        for info in slicer_info:
            coords = info["coords"]
            angles = info["angles"]
            xyz_line = "{:f} {:f} {:f}\n".format(coords[0], coords[1], coords[2])
            xyz_motl_file.write(xyz_line)
            motl_line = "{:f} {:f} {:f}\n".format(angles[0], angles[1], angles[2])
            eulers_motl_file.write(motl_line)

        xyz_motl_file.close()
        eulers_motl_file.close()


def copy_over_imod_files(imod_root, artia_root, dir_starts_with, real_data_mode=False, mod_contains=None):
    for subdir in os.listdir(imod_root):
        if subdir.startswith(dir_starts_with):

            # Look for the necessary IMOD files
            xf = ""
            tlt = ""
            stack = ""
            mod = ""
            if not real_data_mode:
                mod = "none"
            for file in os.listdir(os.path.join(imod_root, subdir)):
                if file.endswith(".tlt") and not file.endswith("_fid.tlt"):
                    tlt = file
                elif file.endswith(".st"):
                    stack = file
                elif file.endswith(".xf"):
                    xf = file
                if real_data_mode and mod_contains in file and file.endswith(".mod"):
                    mod = file

                # Break out of loop once all three relevant files have been found
                if tlt != "" and stack != "" and xf != "" and mod != "":
                    break

            artia_stack_dir = os.path.join(artia_root, subdir)
            if not os.path.exists(artia_stack_dir):
                os.mkdir(artia_stack_dir)

            # Copy over the stack to the Artiatomi folder
            if stack != "":
                shutil.copyfile(os.path.join(imod_root, subdir, stack), os.path.join(artia_stack_dir, stack))
            else:
                print("ERROR: No tiltseries was found for sub-directory: %s" % subdir)
                exit(1)

            # Copy over the tlt file to the Artiatomi folder
            if tlt != "":
                shutil.copyfile(os.path.join(imod_root, subdir, tlt), os.path.join(artia_stack_dir, tlt))
            else:
                print("WARNING: No .tlt file was found for sub-directory: %s" % subdir)

            # Copy over the tlt file to the Artiatomi folder
            if xf != "":
                shutil.copyfile(os.path.join(imod_root, subdir, xf), os.path.join(artia_stack_dir, xf))
            else:
                print("WARNING: No .xf file was found for sub-directory: %s" % subdir)

            if real_data_mode:
                # Copy over the mod file to the Artiatomi folder
                if mod != "":
                    shutil.copyfile(os.path.join(imod_root, subdir, mod), os.path.join(artia_stack_dir, mod))
                else:
                    print("WARNING: No .mod file was found for sub-directory: %s" % subdir)


def setup_reconstructions_script(root, name, artia_args):
    """
    Function to generate the Artiatomi reconstruction setup script

    Args:
        root: The ETSimulations project root (only used for coming from simulated data)
        name: The project/particle name (only used for coming from simulated data)
        artia_args: The Artiatomi Processor arguments

    Returns: None

    """
    xyz_motl = "%s_xyz.txt" % name
    eulers_motl = "%s_motl.txt" % name

    # Get input parameters based on mode
    if artia_args["real_data_mode"]:
        artia_root = artia_args["artia_dir"]
        imod_root = artia_args["imod_dir"]
        dir_starts_with = artia_args["dir_starts_with"]
        mod_contains = artia_args["mod_contains"]
    else:
        artia_root = os.path.join(root, "processed_data", "Artiatomi")
        imod_root = os.path.join(root, "processed_data", "IMOD")
        dir_starts_with = name
        mod_contains = ""

    # -------------------------------------
    # Set up Artiatomi project directory structure
    # -------------------------------------
    print("Creating Artiatomi project directories")
    if not os.path.exists(artia_root):
        os.mkdir(artia_root)

    copy_over_imod_files(imod_root, artia_root, dir_starts_with, real_data_mode=artia_args["real_data_mode"],
                         mod_contains=mod_contains)

    if artia_args["real_data_mode"]:
        write_out_motl_files_real(artia_root, xyz_motl, eulers_motl)
    else:
        write_out_motl_files_simulated(root, name, xyz_motl, eulers_motl)

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
                    elif variable_name == "xyz_motl":
                        value_to_write_out = f"\'{xyz_motl}\';"
                    elif variable_name == "eulers_motl":
                        value_to_write_out = f"\'{eulers_motl}\';"
                    elif variable_name in artia_args:
                        value_to_write_out = f"\'{artia_args[variable_name]}\';"
                    else:
                        print("Missing Artiatomi processing parameter: %s!" % variable_name)
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

    if "setup_reconstructions_and_motls" in artia_args and artia_args["setup_reconstructions_and_motls"]:
        setup_reconstructions_script(root, name, artia_args)
