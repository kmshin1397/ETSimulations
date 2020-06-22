""" This module implements the processing function for the I3 software package.

The module will create an I3 project directory.
"""

import os
import struct
import shutil
import mrcfile
import numpy as np
from scipy.spatial.transform import Rotation as R
import subprocess, shlex
import json


def convert_tlt(map_file, tilt_angle, file_in, file_out):
    """
    Convert an IMOD .tlt file to I3 tilt file format
    Args:
        map_file: The map MRC file
        tilt_angle: The angle to put as the tilt azimuth
        file_in: The IMOD .tlt file
        file_out: The I3 tilt file

    Returns: None

    """

    lines = ["TILT SERIES %s" % map_file,
             "",
             "  AXIS",
             "",
             "    TILT AZIMUTH    %f" % tilt_angle,
             "",
             "",
             "  ORIENTATION",
             "    PHI    0.000"]

    angles = np.loadtxt(file_in)
    line = ""
    for i, angle in enumerate(angles):
        line = "  IMAGE %03d" % (i + 1)
        line += "       ORIGIN [  0.000   0.000 ]"
        line += "    TILT ANGLE   %.3f" % angle
        line += "    ROTATION     0.000"

    lines.append(line)
    lines.extend(["", "", "END"])

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
    with mrcfile.open(rec, header_only=True) as mrc:
        x = mrc.header.nx
        y = mrc.header.ny
        z = mrc.header.nz

        return float(x) / 2, float(y) / 2, float(z) / 2


def center_coordinates(coords, size):
    """
    Given an XYZ tuple of particle coordinates and the reconstruction they came from, shift the
        coordinates so that the origin is at the center of the tomogram

    Args:
        coords: the (x, y, z) coordinates for the particle
        size: the reconstruction MRC half-dimensions in (nx/2, ny/2, nz/2) form

    Returns: the new coordinates as a (x, y, z) tuple

    """
    return coords[0] - size[0], coords[1] - size[1], coords[2] - size[2]


def get_slicer_info(mod_file):
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
    Given the Slicer angles, convert them to the PEET MOTL angles, then feed those into a call of
        i3avg to get the I3 rotation matrix

    Args:
        angles: The Slicer angles

    Returns: The rotation matrix as a 1D Numpy array

    """

    # Slicer stores angles in XYZ order even though rotations are applied as ZYX, so we flip here
    rot = R.from_euler('zyx', [angles[2], angles[1], angles[0]], degrees=True)
    # The Slicer angles are particle-to-reference, but PEET MOTLs are ref-to-part, so we invert
    rot = rot.inv()
    motl = rot.as_euler('zxz', degrees=True)

    command = "i3euler %f %f %f" % (motl[0], motl[2], motl[1])

    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
    matrix_str = ""
    while True:
        output = os.fsdecode(process.stdout.readline())
        if output == '' and process.poll() is not None:
            break
        if output:
            matrix_str = output.strip()

    rc = process.poll()
    if rc != 0:
        exit(1)

    matrix = np.fromstring(matrix_str, sep=" ")
    return matrix
    # matrix = np.array(rot.as_matrix()).flatten()
    # return matrix


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


def get_trf_lines(slicer_info, basename):
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
    i3_root = processed_data_dir + "/I3"
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
                shutil.copyfile(os.path.join(root, tomogram_dir, rec), os.path.join(maps_path, rec))
            else:
                print("ERROR: No reconstruction was found for sub-directory: %s" % tomogram_dir)
                exit(1)

            tlt = "%s.tlt" % basename
            # Copy over the tlt file to the maps folder
            if os.path.exists(os.path.join(tomogram_dir, tlt)):
                convert_tlt(rec, i3_args["tlt_angle"], os.path.join(tomogram_dir, tlt),
                            os.path.join(maps_path, tlt))
            else:
                print("WARNING: No tlt file was found for sub-directory: %s" % tomogram_dir)

            # Add the tomogram info to the defs/maps file
            print("Updating the maps file...")
            new_maps_line = "../maps %s ../maps/%s\n" % (rec, tlt)
            maps_file.write(new_maps_line)

            # Add the tomogram info to the defs/sets file
            print("Updating the sets file...")
            new_sets_line = "%s %s_%s\n" % (rec, basename, name)
            sets_file.write(new_sets_line)

            # Read the .mod file info
            print("Shifting the origins to the center for the particle coordinates...")
            rec_fullpath = os.path.join(root, tomogram_dir, rec)
            size = get_mrc_size(rec_fullpath)
            for particle in slicer_info:
                # Shift the coordinates to have the origin at the tomogram center
                particle["coords"] = center_coordinates(particle["coords"], size)

            # Write the trf file for this tomogram
            print("Writing the .trf file...")
            trf_filepath = os.path.join(trf_path, "%s_%s.trf" % (basename, name))
            with open(trf_filepath, 'w') as trf:
                lines = get_trf_lines(slicer_info, "%s_%s" % (basename, name))
                trf.writelines(lines)

    # Close files
    maps_file.close()
    sets_file.close()


def imod_real_to_i3(name, i3_args):
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

            # Copy over the tomogram to the maps folder
            if rec != "":
                shutil.copyfile(os.path.join(root, subdir, rec), os.path.join(maps_path, rec))
            else:
                print("ERROR: No reconstruction was found for sub-directory: %s" % subdir)
                exit(1)

            # Copy over the tlt file to the maps folder
            if tlt != "":
                convert_tlt(rec, i3_args["tlt_angle"], os.path.join(root, subdir, tlt),
                            os.path.join(maps_path, tlt))
            else:
                print("WARNING: No tlt file was found for sub-directory: %s" % subdir)

            if mod == "":
                print("Error: No mod file was found for sub-directory: %s" % subdir)
                exit(1)

            # Add the tomogram info to the defs/maps file
            print("Updating the maps file...")
            new_maps_line = "../maps %s ../maps/%s\n" % (rec, tlt)
            maps_file.write(new_maps_line)

            # Add the tomogram info to the defs/sets file
            print("Updating the sets file...")
            new_sets_line = "%s %s_%s\n" % (rec, basename, name)
            sets_file.write(new_sets_line)

            # Read the .mod file info
            print("Reading the .mod file for Slicer info...")
            slicer_info = get_slicer_info(os.path.join(root, subdir, mod))
            print("Shifting the origins to the center for the particle coordinates...")
            rec_fullpath = os.path.join(root, subdir, rec)
            size = get_mrc_size(rec_fullpath)
            for particle in slicer_info:
                # Shift the coordinates to have the origin at the tomogram center
                particle["coords"] = center_coordinates(particle["coords"], size)

            # Write the trf file for this tomogram
            print("Writing the .trf file...")
            trf_filepath = os.path.join(trf_path, "%s_%s.trf" % (basename, name))
            with open(trf_filepath, 'w') as trf:
                lines = get_trf_lines(slicer_info, "%s_%s" % (basename, name))
                trf.writelines(lines)

    # Close files
    maps_file.close()
    sets_file.close()


def i3_main(root, name, i3_args):
    if i3_args["real_data_mode"]:
        imod_real_to_i3(name, i3_args)
    else:
        imod_processor_to_i3(root, name, i3_args)

