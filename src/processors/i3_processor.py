""" This module implements the processing function for the I3 software package.

The module will create an I3 project directory.
"""

import os
import struct
import shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
import subprocess, shlex
import json
import math
import warnings


#################################
#   General Helper Functions    #
#################################
def check_and_fix_names_starting_with_numbers(name):
    """
    Since I3 map names cannot start with a number, add a letter 'a' to any names starting with a
        number

    Args:
        name: The name to check for a beginning number

    Returns: The new name (unchanged if the name properly started with a letter)

    """
    result = name
    if name[0].isdigit():
        result = 'a' + name

    return result


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


def center_coordinates(coords, size, binning=1):
    """
    Given an XYZ tuple of particle coordinates and the reconstruction they came from, shift the
        coordinates so that the origin is at the center of the tomogram

    Args:
        coords: the (x, y, z) coordinates for the particle
        size: the reconstruction MRC half-dimensions in (nx/2, ny/2, nz/2) form
        binning: the bin factor from the original stack to the final reconstruction

    Returns: the new coordinates as a (x, y, z) tuple

    """
    return float(coords[0]) / binning - size[0], float(coords[1]) / binning - size[1], \
           float(coords[2]) / binning - size[2]


def split_coords(coords):
    """
    Given XYZ coordinates, split into the integer positions and displacements from the integer
        position, as required by the trf files

    Args:
        coords: The X, Y, Z coordinates

    Returns: tuple (icoor, diff_coord) of the integer and decimal parts, respectively

    """
    npcoord = np.array(coords)

    # integer part
    icoord = npcoord.astype(int)

    # decimal part:
    diff_coord = npcoord - icoord

    return icoord, diff_coord


######################################
#   IMOD-related Helper Functions    #
######################################

def get_trf_lines_imod(slicer_info, basename):
    """
    Given the particle coordinates and angles for a tomogram, format them into a list of lines to
        write out to a .trf file
    Args:
        slicer_info: A list of dictionary objects with keys {"coords", "angles"} for the particles
            in a tomogram (returned from get_slicer_info())
        basename: A basename for the tomogram, to be put as the data subset identifier for the .trf

    Returns: A list of lines to write out to a .trf file

    """
    lines = []
    for particle in slicer_info:
        coords = particle["coords"]
        angles = particle["angles"]

        # Add data subset identifier first
        new_line = "%s " % basename

        # Add the particle position
        ints, displacements = split_coords(coords)
        new_line += "%d %d %d " % (ints[0], ints[1], ints[2])
        new_line += "%f %f %f " % (displacements[0], displacements[1], displacements[2])

        # Add the rotation matrix
        rot_matrix = slicer_angles_to_i3_matrix(angles)
        new_line += "%f %f %f %f %f %f %f %f %f\n" % \
                    (rot_matrix[0], rot_matrix[1], rot_matrix[2],
                     rot_matrix[3], rot_matrix[4], rot_matrix[5],
                     rot_matrix[6], rot_matrix[7], rot_matrix[8])

        lines.append(new_line)

    return lines


def convert_tlt_imod(map_file, tilt_angle, file_in, file_out):
    """
    Convert an IMOD .tlt file to I3 tilt file format
    Args:
        map_file: The map MRC file (not the full path)
        tilt_angle: The angle to put as the tilt azimuth
        file_in: The IMOD .tlt file
        file_out: The I3 tilt file

    Returns: None

    """

    lines = ["TILT SERIES %s\n" % map_file,
             "\n",
             "  AXIS\n",
             "\n",
             "    TILT AZIMUTH    %f\n" % tilt_angle,
             "\n",
             "\n",
             "  ORIENTATION\n",
             "    PHI    0.000\n"]

    angles = np.loadtxt(file_in)
    for i, angle in enumerate(angles):
        line = "  IMAGE %03d" % (i + 1)
        line += "       ORIGIN [  0.000   0.000 ]"
        line += "    TILT ANGLE   %.3f" % angle
        line += "    ROTATION     0.000\n"
        lines.append(line)

    lines.extend(["\n", "\n", "END"])

    with open(file_out, "w") as f:
        f.writelines(lines)


def get_mrc_size(rec):
    """
    Return the half the size of each dimension for an MRC file, so that we can move the origin to
        the center instead of the corner of the file

    Args:
        rec: the MRC file to get the size of

    Returns: A tuple (x/2, y/2, z/2) of the half-lengths in each dimension

    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import mrcfile

        with mrcfile.open(rec, mode='r', header_only=True, permissive=True) as mrc:
            x = mrc.header.nx
            y = mrc.header.ny
            z = mrc.header.nz

            return float(x) / 2, float(y) / 2, float(z) / 2


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


def slicer_angles_to_i3_matrix(angles):
    """
    Given a set of angles from IMOD's Slicer, convert those angles to a rotation matrix.

    Args:
        angles: The (x, y, z) Slicer angles

    Returns:
        The corresponding rotation matrix

    """

    # Note: The i3euler program will take ZXZ euler angles and invert that rotation before
    # converting it to a rotation matrix. Thus, previous workflows had conversions from the Slicer
    # angles to the PEET MOTL angles (which inverts the rotation since Slicer is particle-to-ref and
    # PEET MOTLs use ref-to-particle) before feeding those angles into i3euler. We can skip all
    # those steps by just converting the Slicer angles to a rotation matrix.

    # Slicer stores angles in XYZ order even though rotations are applied as ZYX, so we flip here
    rot = R.from_euler('zyx', [angles[2], angles[1], angles[0]], degrees=True)
    matrix = np.array(rot.as_matrix()).flatten()
    return matrix


############################
#   IMOD Main Functions    #
############################

def imod_processor_to_i3(root, name, i3_args):
    """
    Implements the I3 processing of simulated data that was reconstructed using the IMOD Processor.

    Args:
        root: The ETSimulations project root directory
        name: The particle name
        i3_args: The I3 Processor arguments

    Returns: None

    """

    # -------------------------------------
    # Set up I3 project directory structure
    # -------------------------------------
    print("Creating I3 project directories")
    processed_data_dir = root + "/processed_data"
    i3_root = processed_data_dir + "/I3-from-IMOD"
    if not os.path.exists(i3_root):
        os.mkdir(i3_root)

    # Copy over mraparam.sh file
    shutil.copyfile(i3_args["mraparam_path"], os.path.join(i3_root, "mraparam.sh"))

    # Make the maps folder if necessary
    maps_path = os.path.join(i3_root, "maps")
    if not os.path.exists(maps_path):
        os.mkdir(maps_path)

    # Make the defs folder if necessary
    defs_path = os.path.join(i3_root, "defs")
    maps_file_path = os.path.join(defs_path, "maps")
    sets_file_path = os.path.join(defs_path, "sets")
    if not os.path.exists(defs_path):
        os.mkdir(defs_path)
    maps_file = open(maps_file_path, "w")
    sets_file = open(sets_file_path, "w")

    # Make the trf folder if necessary
    trf_path = os.path.join(i3_root, "trf")
    if not os.path.exists(trf_path):
        os.mkdir(trf_path)

    # Iterate through the tomograms in the order they appear in the metadata file instead of just
    # iterating through the processed IMOD directory like with the real data version of this
    # function. This is faster since we avoid searching through the metadata dictionary to match up
    # data directories to the original raw data metadata.

    metadata_file = os.path.join(root, "sim_metadata.json")

    # Load IMOD Processor info
    processor_info_file = os.path.join(root, "processed_data/imod_info.json")
    processor_info = json.load(open(processor_info_file, "r"))["args"]

    with open(metadata_file, "r") as f:
        metadata = json.loads(f.read())

        # -------------------------------------
        # Retrieve parameters to write to files
        # -------------------------------------
        total_num = len(metadata)
        for num, tomogram in enumerate(metadata):
            basename = "%s_%d" % (name, tomogram["global_stack_no"])
            tomogram_dir = os.path.join(root, "processed_data/IMOD", basename)
            print("")
            print("Collecting information for directory: %s" % tomogram_dir)
            print("This is directory %d out of %d" % (num + 1, total_num))

            # Positions for TEM-Simulator are in nm, need to convert to pixels
            positions = np.array(tomogram["positions"]) / tomogram["apix"]
            # During reconstruction, there is a 90 degree rotation around the z-axis, so correct for
            # that with the positions
            positions = rotate_positions_around_z(positions)

            slicer_angles_csv = os.path.join(tomogram_dir, "%s_slicerAngles.csv" % name)
            print("Loading Slicer angles...")
            orientations = np.loadtxt(slicer_angles_csv, delimiter=",")

            # Compile Slicer infos
            slicer_info = []
            for i, coords in enumerate(positions):
                angles = orientations[i]
                slicer_info.append({"coords": coords, "angles": angles})

            # Look for the necessary IMOD files
            print("Looking for necessary IMOD files...")
            if processor_info["reconstruction_method"].startswith("imod"):
                if processor_info["binvol"]:
                    rec = "%s_full_bin%d.mrc" % (basename, processor_info["binvol"]["binning"])
                else:
                    rec = "%s_full.rec" % basename
            else:
                if processor_info["binvol"]:
                    rec = "%s_SIRT_bin%d.mrc" % (basename, processor_info["binvol"]["binning"])
                else:
                    rec = "%s_SIRT.mrc" % basename

            # Copy over the tomogram to the maps folder
            if os.path.exists(os.path.join(tomogram_dir, rec)):
                shutil.copyfile(os.path.join(root, tomogram_dir, rec),
                                os.path.join(maps_path,
                                             check_and_fix_names_starting_with_numbers(rec)))
            else:
                print("ERROR: No reconstruction was found for sub-directory: %s" % tomogram_dir)
                exit(1)

            tlt = "%s.tlt" % basename
            # Copy over the tlt file to the maps folder
            if os.path.exists(os.path.join(tomogram_dir, tlt)):
                convert_tlt_imod(rec, i3_args["tlt_angle"], os.path.join(tomogram_dir, tlt),
                                 os.path.join(maps_path,
                                              check_and_fix_names_starting_with_numbers(tlt)))
            else:
                print("WARNING: No tlt file was found for sub-directory: %s" % tomogram_dir)

            # Add the tomogram info to the defs/maps file
            print("Updating the maps file...")
            new_maps_line = "../maps %s ../maps/%s\n" % \
                            (check_and_fix_names_starting_with_numbers(rec),
                             check_and_fix_names_starting_with_numbers(tlt))
            maps_file.write(new_maps_line)

            basename = check_and_fix_names_starting_with_numbers(basename)
            # Add the tomogram info to the defs/sets file
            print("Updating the sets file...")
            new_sets_line = "%s %s_%s\n" % (check_and_fix_names_starting_with_numbers(rec),
                                            basename, name)
            sets_file.write(new_sets_line)

            # Read the .mod file info
            print("Shifting the origins to the bottom-left for the particle coordinates...")
            rec_fullpath = os.path.join(root, tomogram_dir, rec)
            size = get_mrc_size(rec_fullpath)
            if "binvol" in processor_info:
                binning = processor_info["binvol"]["binning"]
            else:
                binning = 1

            for particle in slicer_info:
                # Shift the coordinates to have the origin at the tomogram bottom-left
                particle["coords"] = shift_coordinates_bottom_left(particle["coords"], size,
                                                                   binning)

            # Write the trf file for this tomogram
            print("Writing the .trf file...")
            trf_filepath = os.path.join(trf_path, "%s_%s.trf" % (basename, name))
            with open(trf_filepath, 'w') as trf:
                lines = get_trf_lines_imod(slicer_info, "%s_%s" % (basename, name))
                trf.writelines(lines)

    # Close files
    maps_file.close()
    sets_file.close()


def imod_real_to_i3(name, i3_args):
    """
    Implements the I3 processing of a real data set reconstructed/particle-picked with IMOD

    Args:
        name: The particle name
        i3_args: The I3 Processor arguments

    Returns: None
    """

    root = i3_args["imod_dir"]

    # -------------------------------------
    # Set up I3 project directory structure
    # -------------------------------------
    print("Creating I3 project directories")
    i3_root = i3_args["i3_dir"]
    if not os.path.exists(i3_root):
        os.mkdir(i3_root)

    # Make the maps folder if necessary
    maps_path = os.path.join(i3_root, "maps")
    if not os.path.exists(maps_path):
        os.mkdir(maps_path)

    # Make the defs folder if necessary
    defs_path = os.path.join(i3_root, "defs")
    maps_file_path = os.path.join(defs_path, "maps")
    sets_file_path = os.path.join(defs_path, "sets")
    if not os.path.exists(defs_path):
        os.mkdir(defs_path)
    maps_file = open(maps_file_path, "w")
    sets_file = open(sets_file_path, "w")

    # Make the trf folder if necessary
    trf_path = os.path.join(i3_root, "trf")
    if not os.path.exists(trf_path):
        os.mkdir(trf_path)

    shutil.copyfile(i3_args["mraparam_path"], os.path.join(i3_root, "mraparam.sh"))

    # -------------------------------------
    # Retrieve parameters to write to files
    # -------------------------------------
    for subdir in os.listdir(root):
        if subdir.startswith(i3_args["dir_contains"]):
            print("")
            print("Collecting information for directory: %s" % subdir)

            # Look for the necessary IMOD files
            mod = ""
            tlt = ""
            rec = ""
            for file in os.listdir(os.path.join(root, subdir)):
                if i3_args["mod_contains"] in file and file.endswith(".mod"):
                    mod = file
                elif i3_args["tlt_contains"] in file and file.endswith(".tlt"):
                    tlt = file
                elif i3_args["rec_contains"] in file and (file.endswith(".mrc") or
                                                          file.endswith(".rec")):
                    rec = file

                # Break out of loop once all three relevant files have been found
                if mod != "" and tlt != "" and rec != "":
                    break

            basename = os.path.splitext(rec)[0]
            basename = check_and_fix_names_starting_with_numbers(basename)

            # Copy over the tomogram to the maps folder
            if rec != "":
                shutil.copyfile(os.path.join(root, subdir, rec),
                                os.path.join(maps_path,
                                             check_and_fix_names_starting_with_numbers(rec)))
            else:
                print("ERROR: No reconstruction was found for sub-directory: %s" % subdir)
                exit(1)

            # Copy over the tlt file to the maps folder
            if tlt != "":
                convert_tlt_imod(rec, i3_args["tlt_angle"], os.path.join(root, subdir, tlt),
                                 os.path.join(maps_path,
                                              check_and_fix_names_starting_with_numbers(tlt)))
            else:
                print("WARNING: No tlt file was found for sub-directory: %s" % subdir)

            if mod == "":
                print("Error: No mod file was found for sub-directory: %s" % subdir)
                exit(1)

            # Add the tomogram info to the defs/maps file
            print("Updating the maps file...")
            new_maps_line = "../maps %s ../maps/%s\n" % \
                            (check_and_fix_names_starting_with_numbers(rec),
                             check_and_fix_names_starting_with_numbers(tlt))
            maps_file.write(new_maps_line)

            # Add the tomogram info to the defs/sets file
            print("Updating the sets file...")
            new_sets_line = "%s %s_%s\n" % (check_and_fix_names_starting_with_numbers(rec),
                                            basename, name)
            sets_file.write(new_sets_line)

            # Read the .mod file info
            print("Reading the .mod file for Slicer info...")
            slicer_info = get_slicer_info(os.path.join(root, subdir, mod))

            # Write the trf file for this tomogram
            print("Writing the .trf file...")
            trf_filepath = os.path.join(trf_path, "%s_%s.trf" % (basename, name))
            with open(trf_filepath, 'w') as trf:
                lines = get_trf_lines_imod(slicer_info, "%s_%s" % (basename, name))
                trf.writelines(lines)

    # Close files
    maps_file.close()
    sets_file.close()


#######################################
#   EMAN2-related Helper Functions    #
#######################################

def extract_e2_particles(stack_file, name, destination):
    """
    Unpack a stack of EMAN2 particles into individual sub-volume maps

    Args:
        stack_file: The EMAN2 particle stack file (either a .lst set or .hdf stack)
        name: The basename to assign to extracted maps
        destination: The destination folder to place the extracted particles in

    Returns: None

    """
    name = check_and_fix_names_starting_with_numbers(name)
    command = "e2proc3d.py --unstacking %s %s/%s.mrc" % (stack_file, destination, name)
    print(command)
    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
    while True:
        output = os.fsdecode(process.stdout.readline())
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
    rc = process.poll()
    if rc != 0:
        exit(1)


def read_particle_params(json_file):
    """
    Given a particle_parms_*.json file from EMAN2 STA, extract the particle list and their
        transformation matrices.

    Args:
        json_file: The particle_parms_*.json file path

    Returns: A tuple of (.lst file name, dictionary of {particle number, transformation matrix})

    """

    lst_file = ""
    jdict = {}

    with open(json_file) as f:
        data = json.load(f)

        for key, value in data.items():
            tokens = key.split("\', ")
            particle_no = int(tokens[1].split(")")[0])
            lst_file = tokens[0].split("\'")[1]

            matrix = value['xform.align3d']['matrix']
            jdict[particle_no] = matrix

    return lst_file, jdict


def parse_lst_file(filename):
    """
    Read EMAN2 .lst particle sets and extract a dictionary of particle numbers mapped to the
        particle's tomogram info file, extracted stack file, and local particle number within that
        tomogram

    Args:
        filename: The .lst file path

    Returns: A tuple of
        (
            Dictionary of { particle number: {"info", "stack", "local_no"} } objects,
            Dictionary of { stack: number of particles in stack }
        )

    """

    # Dictionary mapping global particle numbers to info JSONs and stacks
    ldict = {}

    # Return just a set of the stacks as well for easier access later with their number of particles
    stacks = {}

    with open(filename) as f:
        for i, line in enumerate(f):
            # Skip first 3 lines which should be comments
            if i >= 3 and line != "":
                global_particle_no = i - 3
                tokens = line.strip().split()
                stack = tokens[1]
                basename = os.path.basename(stack).split("__")[0]
                info_file = "info/{:s}_info.json".format(basename)
                num = int(tokens[0]) + 1
                ldict[global_particle_no] = {"info": info_file, "stack": stack, "local_no": num}

                # If this is the largest particle number encountered for this stack file so far
                if stack not in stacks or stacks[stack] < num:
                    stacks[stack] = num

    return ldict, stacks


def get_eman2_tilts(info_file):
    """
    Given an EMAN2 tomogram info JSON file, extract an array of the tilt angles as would be given in
        an IMOD .tlt file

    Args:
        info_file: The tomogram JSON info file path

    Returns: A tuple of (average tilt axis computed across all tilts,
        a numpy array of the tilt angles for that tomogram)
    """
    with open(info_file, "r") as f:
        info = json.load(f)
        tlt_params = np.array(info["tlt_params"])
        tlt_angles = tlt_params[:, 3]
        tilt_axis = np.mean(tlt_params[:, 2])

        return tilt_axis, tlt_angles


def convert_tlt_eman2(info_file, map_file, output):
    """
    Given an EMAN2 tomogram info JSON file, write out an I3 format .tlt file for that tomogram

    Args:
        info_file: The EMAN2 JSON info file for the tomogram
        map_file: The map file to place at the head of the .tlt file
        output: The output file path to write the new I3 .tlt file to

    Returns: None
    """

    tilt_axis, tlt_angles = get_eman2_tilts(info_file)
    lines = ["TILT SERIES %s\n" % map_file,
             "\n",
             "  AXIS\n",
             "\n",
             "    TILT AZIMUTH    %f\n" % tilt_axis,
             "\n",
             "\n",
             "  ORIENTATION\n",
             "    PHI    0.000\n"]

    for i, angle in enumerate(tlt_angles):
        line = "  IMAGE %03d" % (i + 1)
        line += "       ORIGIN [  0.000   0.000 ]"
        line += "    TILT ANGLE   %.3f" % angle
        line += "    ROTATION     0.000\n"
        lines.append(line)

    lines.extend(["\n", "\n", "END"])

    with open(output, "w") as f:
        f.writelines(lines)


def write_trf_eman2_extracted(set_name, translations, rot_matrix, trf_file):
    """
    Helper function to write out the .trf file for one extracted particle

    Args:
        set_name: The I3 set name to write (should be the basename of the extracted map file)
        translations: The particle translations
        rot_matrix: The rotation matrix for the particle
        trf_file: The output file path

    Returns: None

    """
    with open(trf_file, "w") as f:
        a0 = set_name
        a1, a2, a3 = (0, 0, 0)
        a4, a5, a6 = translations

        f.write("{0}   {1} {2} {3} {4:.2f} {5:.2f} {6:.2f}   ".format(a0, a1, a2, a3, a4, a5, a6))
        f.write("%f %f %f %f %f %f %f %f %f" %
                (rot_matrix[0], rot_matrix[1], rot_matrix[2],
                 rot_matrix[3], rot_matrix[4], rot_matrix[5],
                 rot_matrix[6], rot_matrix[7], rot_matrix[8]))


#############################
#   EMAN2 Main Functions    #
#############################

def eman2_real_to_i3(i3_args):
    """
    Implements the I3 processing of a real data set reconstructed/particle-picked with EMAN2

    Args:
        i3_args: The I3 Processor arguments

    Returns: None
    """
    json_file = i3_args["params_json"]
    lst, particles = read_particle_params(json_file)
    lst_file = os.path.join(i3_args["eman2_dir"], lst)

    if "lst_file" in i3_args:
        lst_file = i3_args["lst_file"]

    lst_entries, stacks_info = parse_lst_file(lst_file)

    # -------------------------------------
    # Set up I3 project directory structure
    # -------------------------------------
    print("\nCreating I3 project directories")
    i3_root = i3_args["i3_dir"]
    if not os.path.exists(i3_root):
        os.mkdir(i3_root)

    # Make the maps folder if necessary
    maps_path = os.path.join(i3_root, "maps")
    if not os.path.exists(maps_path):
        os.mkdir(maps_path)

    # Make the defs folder if necessary
    defs_path = os.path.join(i3_root, "defs")
    maps_file_path = os.path.join(defs_path, "maps")
    sets_file_path = os.path.join(defs_path, "sets")
    if not os.path.exists(defs_path):
        os.mkdir(defs_path)
    maps_file = open(maps_file_path, "w")
    sets_file = open(sets_file_path, "w")

    # Make the trf folder if necessary
    trf_path = os.path.join(i3_root, "trf")
    if not os.path.exists(trf_path):
        os.mkdir(trf_path)

    shutil.copyfile(i3_args["mraparam_path"], os.path.join(i3_root, "mraparam.sh"))

    # -------------------------------------
    # Set up I3 project directory contents
    # -------------------------------------

    # Extract individual particle maps from the stacks
    print("\nExtracting individual particle maps...")
    for stack in stacks_info.keys():
        basename = os.path.basename(stack).split(".")[0]
        extract_e2_particles(os.path.join(i3_args["eman2_dir"], stack), basename,
                             maps_path)

    # Extract individual particle maps into maps folder
    num_particles = len(particles)
    progress = 1
    for particle_no, transformation_matrix in particles.items():
        print("\nWorking on particle {:d} out of {:d}..".format(progress, num_particles))
        lst_entry = lst_entries[particle_no]
        stack_base = os.path.basename(lst_entry["stack"]).split(".")[0]
        local_particle_no = lst_entry["local_no"]

        num_particles_in_tomogram = stacks_info[lst_entry["stack"]]
        num_digits = math.floor(math.log10(num_particles_in_tomogram)) + 1
        name = check_and_fix_names_starting_with_numbers(stack_base)
        particle_map = "{:s}-{:0{:d}d}".format(name, local_particle_no, num_digits)

        print("Creating tlt file and updating the maps file...")
        info_file = os.path.join(i3_args["eman2_dir"], lst_entry["info"])
        new_tlt_file = os.path.join(maps_path, particle_map + ".tlt")
        convert_tlt_eman2(info_file, particle_map + ".mrc", new_tlt_file)

        new_maps_line = "../maps {:s}.mrc ../maps/{:s}.tlt\n".format(particle_map, particle_map)
        maps_file.write(new_maps_line)

        # Add the particle info to the defs/sets file
        print("Updating the sets file...")
        new_sets_line = "{:s}.mrc {:s}\n".format(particle_map, particle_map)
        sets_file.write(new_sets_line)

        # write to a .trf file in folder trf
        print("Writing the .trf file...")
        trf_filepath = os.path.join(trf_path, "%s.trf" % particle_map)
        # Convert EMAN2 transformation matrix to a rotation matrix
        a1, a2, a3 = tuple(transformation_matrix[0:3])
        a4, a5, a6 = tuple(transformation_matrix[4:7])
        a7, a8, a9 = tuple(transformation_matrix[8:11])
        translations = (transformation_matrix[3], transformation_matrix[7],
                        transformation_matrix[11])
        rot_matrix = [a1, a2, a3, a4, a5, a6, a7, a8, a9]
        write_trf_eman2_extracted(particle_map, translations, rot_matrix, trf_filepath)

        progress += 1

    maps_file.close()
    sets_file.close()


def eman2_processor_to_i3(root, name, i3_args):
    """
    Implements the I3 processing of simulated data that was reconstructed using the EMAN2 Processor.

    Args:
        root: The ETSimulations project root directory
        name: The particle name
        i3_args: The I3 Processor arguments

    Returns: None

    """
    # -------------------------------------
    # Set up I3 project directory structure
    # -------------------------------------
    print("Creating I3 project directories")
    processed_data_dir = root + "/processed_data"
    i3_root = processed_data_dir + "/I3-from-EMAN2"
    if not os.path.exists(i3_root):
        os.mkdir(i3_root)

    # Make the maps folder if necessary
    maps_path = os.path.join(i3_root, "maps")
    if not os.path.exists(maps_path):
        os.mkdir(maps_path)

    # Make the defs folder if necessary
    defs_path = os.path.join(i3_root, "defs")
    maps_file_path = os.path.join(defs_path, "maps")
    sets_file_path = os.path.join(defs_path, "sets")
    if not os.path.exists(defs_path):
        os.mkdir(defs_path)
    maps_file = open(maps_file_path, "w")
    sets_file = open(sets_file_path, "w")

    # Make the trf folder if necessary
    trf_path = os.path.join(i3_root, "trf")
    if not os.path.exists(trf_path):
        os.mkdir(trf_path)

    # Iterate through the tomograms in the order they appear in the metadata file instead of just
    # iterating through the processed IMOD directory like with the real data version of this
    # function. This is faster since we avoid searching through the metadata dictionary to match up
    # data directories to the original raw data metadata.

    metadata_file = os.path.join(root, "sim_metadata.json")

    shutil.copyfile(i3_args["mraparam_path"], os.path.join(i3_root, "mraparam.sh"))

    eman2_dir = os.path.join(processed_data_dir, "EMAN2")

    # -------------------------------------
    # Set up I3 project directory contents
    # -------------------------------------

    with open(metadata_file, "r") as f:
        metadata = json.loads(f.read())

        # -------------------------------------
        # Retrieve parameters to write to files
        # -------------------------------------
        total_num = len(metadata)
        for num, tomogram in enumerate(metadata):
            basename = "%s_%d" % (name, tomogram["global_stack_no"])

            info_file = os.path.join(root, "processed_data/EMAN2/info",
                                     "{:s}_info.json".format(basename))

            print("")
            print("\nCollecting information for %s" % basename)
            print("This is tomogram %d out of %d" % (num + 1, total_num))

            raw_orientations = tomogram["orientations"]
            matrices = []
            for i, row in enumerate(raw_orientations):
                # In ZXZ
                # ETSimulations/TEM-Sim gives ref-to-part, external;
                # rotate by z to account for reconstruction rotation
                euler = [-row[2] - 90, -row[1], -row[0]]  # now at part-to-ref, ext

                # TEM-Simulator is in stationary zxz
                rotation = R.from_euler('zxz', euler, degrees=True)

                matrices.append(np.array(rotation.as_matrix()).flatten())

            print("\nExtracting individual particle maps for the tomogram...")
            expected_stack = os.path.join(eman2_dir, "particles3d",
                                          "{:s}__{:s}.hdf".format(basename, name))

            if os.path.exists(expected_stack):
                extract_e2_particles(expected_stack, basename, maps_path)

                # Convert all the HDF files to MRCs
                num_particles_in_tomogram = len(matrices)
                num_digits = math.floor(math.log10(num_particles_in_tomogram)) + 1
                print("")
                for i in range(num_particles_in_tomogram):
                    print("Updating I3 files for particle %d of %d for the tomogram..." %
                          (i + 1, num_particles_in_tomogram))
                    particle_num = i + 1
                    basename = check_and_fix_names_starting_with_numbers(basename)
                    particle_map = "{:s}-{:0{:d}d}".format(basename, particle_num, num_digits)

                    new_tlt_file = os.path.join(maps_path, particle_map + ".tlt")
                    convert_tlt_eman2(info_file, particle_map + ".mrc", new_tlt_file)

                    # Add the tomogram info to the defs/maps file`
                    new_maps_line = "../maps %s ../maps/%s\n" % (particle_map + ".mrc",
                                                                 particle_map + ".tlt")
                    maps_file.write(new_maps_line)

                    # Add the tomogram info to the defs/sets file
                    new_sets_line = "%s %s\n" % (particle_map + ".mrc", particle_map)
                    sets_file.write(new_sets_line)

                    # Write the trf file for this tomogram
                    trf_filepath = os.path.join(trf_path, "%s.trf" % particle_map)
                    rot_matrix = matrices[i]
                    translations = (0.0, 0.0, 0.0)
                    write_trf_eman2_extracted(particle_map, translations, rot_matrix, trf_filepath)

            else:
                print("ERROR: Missing particle stack: particles3d/%s" %
                      "{:s}__{:s}.hdf".format(basename, name))
                exit(1)

    # Close files
    maps_file.close()
    sets_file.close()


def i3_main(root, name, i3_args):
    if i3_args["source_type"] == "imod":
        if i3_args["real_data_mode"]:
            imod_real_to_i3(name, i3_args)
        else:
            imod_processor_to_i3(root, name, i3_args)
    elif i3_args["source_type"] == "eman2":
        if i3_args["real_data_mode"]:
            eman2_real_to_i3(i3_args)
        else:
            eman2_processor_to_i3(root, name, i3_args)
    else:
        print("Error: Invalid I3 'source_type")
        exit(1)
