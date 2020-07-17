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

def imod_setup_sta(artia_root, dirs_start_with):
    """
    Write out the files necessary to run the MATLAB set up script for sub-tomogram averaging in Artiatomi
    Args:
        artia_root: The Artiatomi project directory
        dirs_start_with: A prefix for the data subdirectories within the Artiatomi project

    Returns: Tuple of motive lists file and tomogram numbers file

    """

    initMOTLs = []
    tomonumbers = []
    for subdir in os.listdir(artia_root):
        if subdir.startswith(dirs_start_with):
            motl_name = ""
            for file in os.listdir(os.path.join(artia_root, subdir)):
                if file.endswith("_motl.em"):
                    motl_name = os.path.basename(file)

            motl = os.path.join(artia_root, subdir, motl_name)
            tomo_num = int(subdir.split("_")[-1]) + 1

            initMOTLs.append(motl)
            tomonumbers.append(tomo_num)

    motl_out = os.path.join(artia_root, "motls.txt")
    tomonums_out = os.path.join(artia_root, "tomonums.txt")

    with open(motl_out, 'w') as f:
        f.write(' '.join(map(str, initMOTLs)))

    with open(tomonums_out, 'w') as f:
        f.write(' '.join(map(str, tomonumbers)))

    return motl_out, tomonums_out


def shift_coordinates_bottom_left(coords, size, binning=1):
    """
    Given an XYZ tuple of particle coordinates and the reconstruction they came from, shift the
        coordinates so that the origin is at the bottom-left of the tomogram

    Args:
        coords: the (x, y, z) coordinates for the particle
        size: the reconstruction MRC half-dimensions in (nx/2, ny/2, nz/2) form
        binning: the bin factor from the original stack to the final reconstruction, to be used if
            you are using coordinates based on the original unbinned coordinate system

    Returns: the new coordinates as a (x, y, z) tuple

    """
    return float(coords[0]) / binning + size[0], float(coords[1]) / binning + size[1], \
           float(coords[2]) / binning + size[2]


def write_out_motl_files_simulated(root, name, xyz_name, motl_name, size, binning):
    """
    Iterate through an IMOD Processor project and set up text files for Artiatomi to read in for its marker files

    Args:
        root: The ETSimulations project root
        name: The project/particle name
        xyz_name: The file name to give each XYZ coordinates file
        motl_name: The file name to give each Euler angles file
        size: Final tomogram size (for shifting origin of coordinates)
        binning: The binning to apply to the raw coordinates

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
                coords = shift_coordinates_bottom_left(info["coords"], size, binning)
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
            motl_line = "{:f} {:f} {:f}\n".format(angles[0], angles[2], angles[1])
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
                elif file.endswith(".xf") and not file.endswith("_fid.xf"):
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
    print("Creating Artiatomi project directories and copying over relevant IMOD files")
    if not os.path.exists(artia_root):
        os.mkdir(artia_root)

    copy_over_imod_files(imod_root, artia_root, dir_starts_with, real_data_mode=artia_args["real_data_mode"],
                         mod_contains=mod_contains)

    print("Writing out MOTL-related files")
    if artia_args["real_data_mode"]:
        write_out_motl_files_real(artia_root, xyz_motl, eulers_motl)
    else:
        binning = 1
        if "position_binning" in artia_args:
            binning = artia_args["position_binning"]

        size = (artia_args["tomogram_size_x"] / 2, artia_args["tomogram_size_y"] / 2, artia_args["tomogram_size_z"] / 2)
        write_out_motl_files_simulated(root, name, xyz_motl, eulers_motl, size, binning)

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
                        value_to_write_out = f"\'{artia_root}\';"
                    elif variable_name == "dir_starts_with":
                        value_to_write_out = f"\'{dir_starts_with}\';"
                    elif variable_name == "xyz_motl":
                        value_to_write_out = f"\'{xyz_motl}\';"
                    elif variable_name == "eulers_motl":
                        value_to_write_out = f"\'{eulers_motl}\';"
                    elif variable_name in artia_args:
                        if type(artia_args[variable_name]) == str:
                            value_to_write_out = f"\'{artia_args[variable_name]}\';"
                        else:
                            value_to_write_out = str(artia_args[variable_name]) + ";"
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


def generate_reconstructions_script(root, name, artia_args):
    """
    Generate a bash script to run the reconstructions.
    Args:
        root: ETSimulations root (only used if coming from simulated data)
        name: Project/particle name (only used if coming from simulated data)
        artia_args: The Artiatomi processor arguments

    Returns: None

    """
    if artia_args["real_data_mode"]:
        artia_root = artia_args["artia_dir"]
        dir_starts_with = artia_args["dir_starts_with"]
    else:
        artia_root = os.path.join(root, "processed_data", "Artiatomi")
        dir_starts_with = name

    # Use template file to create a bash script to run EmSART on a data set
    current_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    template = current_dir + "../../templates/artiatomi/emsart_reconstruct.sh"
    template_path = os.path.realpath(template)
    new_script = os.path.join(artia_root, "emsart_reconstruct.sh")
    print("")
    print("Creating processing script at: %s" % new_script)

    with open(new_script, "w") as new_file:
        with open(template_path, "r") as base_file:
            while True:
                line = base_file.readline()
                if len(line) == 0:
                    break
                elif line.startswith("for f in"):
                    dir_pattern = f"{artia_root}/{dir_starts_with}*"
                    new_line = f"for f in {dir_pattern}\n"
                    new_file.write(new_line)
                else:
                    new_file.write(line)


def generate_sta_script(artia_root, motls_txt, tomonrs_txt, artia_args):
    """
    Generate the MATLAB script for setting up the Artiatomi sub-tomogram averaging
    Args:
        artia_root: Artiatomi project root directory
        motls_txt: The text file listing the motivelist files for the averaging
        tomonrs_txt: The text file listing the tomogram numbers for the tomograms in the averaging project
        artia_args: The Artiatomi processor arguments

    Returns: None

    """

    mask_file = os.path.join(artia_root, "other", "mask.em")
    wedge_file = os.path.join(artia_root, "other", "wedge.em")
    maskCC_file = os.path.join(artia_root, "other", "maskCC.em")
    global_motl_file = os.path.join(artia_root, "motls", "motl_1.em")
    particles_folder = os.path.join(artia_root, "parts")

    # Use template file to create Matlab script to run the remaining steps
    current_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    template = current_dir + "../../templates/artiatomi/setup_artia_sta.m"
    template_path = os.path.realpath(template)
    new_script = os.path.join(artia_root, "setup_artia_sta.m")
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
                if re.match(r"^%% Load motl", line):
                    break

                # If we are at an assignment line
                elif re.match(r".+ =", line):
                    line = line.strip()
                    tokens = line.split(" ")
                    variable_name = tokens[0]

                    value_to_write_out = ""
                    if variable_name == "motls_txt":
                        value_to_write_out = f"\'{motls_txt}\';"
                    elif variable_name == "tomonrs_txt":
                        value_to_write_out = f"\'{tomonrs_txt}\';"
                    elif variable_name == "maskFile":
                        value_to_write_out = f"\'{mask_file}\';"
                    elif variable_name == "wedgeFile":
                        value_to_write_out = f"\'{wedge_file}\';"
                    elif variable_name == "maskCCFile":
                        value_to_write_out = f"\'{maskCC_file}\';"
                    elif variable_name == "motlFile":
                        value_to_write_out = f"\'{global_motl_file}\';"
                    elif value_to_write_out == "particles_folder":
                        value_to_write_out = f"\'{particles_folder}\';"
                    elif variable_name in artia_args:
                        if type(artia_args[variable_name]) == str:
                            value_to_write_out = f"\'{artia_args[variable_name]}\';"
                        else:
                            value_to_write_out = str(artia_args[variable_name]) + ";"
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
                    new_file.write(line)


def artiatomi_main(root, name, artia_args):

    if "setup_reconstructions_and_motls" in artia_args and artia_args["setup_reconstructions_and_motls"]:
        setup_reconstructions_script(root, name, artia_args)

        generate_reconstructions_script(root, name, artia_args)

    if "setup_averaging" in artia_args and artia_args["setup_averaging"]:

        # Get input parameters based on mode
        if artia_args["real_data_mode"]:
            artia_root = artia_args["artia_dir"]
            dir_starts_with = artia_args["dir_starts_with"]
        else:
            artia_root = os.path.join(root, "processed_data", "Artiatomi")
            dir_starts_with = name

        # Set up averaging directory structure
        print("Creating Artiatomi averaging directories")
        sta_dir = os.path.join(artia_root, "sta")
        if not os.path.exists(sta_dir):
            os.mkdir(sta_dir)

        parts_dir = os.path.join(sta_dir, "parts")
        if not os.path.exists(parts_dir):
            os.mkdir(parts_dir)

        motls_dir = os.path.join(sta_dir, "motls")
        if not os.path.exists(motls_dir):
            os.mkdir(motls_dir)

        refs_dir = os.path.join(sta_dir, "refs")
        if not os.path.exists(refs_dir):
            os.mkdir(refs_dir)

        others_dir = os.path.join(sta_dir, "other")
        if not os.path.exists(others_dir):
            os.mkdir(others_dir)

        motls_file, tomonrs_file = imod_setup_sta(artia_root, dir_starts_with)

        generate_sta_script(artia_root, motls_file, tomonrs_file, artia_args)
