""" This module implements the processing function for the EMAN2 software package.

The module will create an EMAN2 project directory and set up a new Python script to process the
raw data from ets_generate_data.py through the EMAN2 tomography pipeline.
"""

import os
import sys
import json
import warnings
from scipy.spatial.transform import Rotation as R
import shutil
import numpy as np
import re


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


######################################
#   IMOD-related Helper Functions    #
######################################

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


def slicer_angles_to_dynamo_angles(angles):
    """
    Given a set of angles from IMOD's Slicer, convert those angles to Dynamo format Euler angles

    Args:
        angles: The (x, y, z) Slicer angles

    Returns:
        The corresponding Euler angles for Dynamo

    """

    # Slicer stores angles in XYZ order even though rotations are applied as ZYX, so we flip here
    rot = R.from_euler('zyx', [angles[2], angles[1], angles[0]], degrees=True)
    rot = rot.as_euler('zxz', degrees=True)

    return [rot[0], rot[1], rot[2]]


def extract_tilt_range(tlt_file):
    """
    Get the minimum and maximum ytilt angles from the .tlt file.

    Args:
        tlt_file: The IMOD .tlt file to parse

    Returns: (ymintilt, ymaxtilt)

    """

    angles = np.loadtxt(tlt_file)

    return round(np.min(angles)), round(np.max(angles))

############################
#   IMOD Main Functions    #
############################


def imod_processor_to_dynamo(root, name, dynamo_args):

    # -----------------------------------------
    # Set up Dynamo project directory structure
    # -----------------------------------------
    print("Creating Dynamo project directories")
    processed_data_dir = root + "/processed_data"
    dynamo_root = processed_data_dir + "/Dynamo-from-IMOD"
    if not os.path.exists(dynamo_root):
        os.mkdir(dynamo_root)

    tomograms_path = dynamo_root + "/tomograms"
    if not os.path.exists(tomograms_path):
        os.mkdir(tomograms_path)

    tomograms_doc_path = dynamo_root + "/tomgrams_noctf_included.doc"
    tomograms_doc_file = open(tomograms_doc_path, "w")

    table_path = dynamo_root + "/table_to_crop_notcf.tbl"
    table_file = open(table_path, "w")

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
        global_particle_num = 1
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
                                os.path.join(tomograms_path, rec))
            else:
                print("ERROR: No reconstruction was found for sub-directory: %s" % tomogram_dir)
                exit(1)

            tlt = "%s.tlt" % basename
            # Parse tilt params
            if os.path.exists(os.path.join(tomogram_dir, tlt)):
                min_tilt, max_tilt = extract_tilt_range(os.path.join(tomogram_dir, tlt))
            else:
                print("WARNING: No tlt file was found for sub-directory: %s" % tomogram_dir)

            tomograms_doc_file.write("{:d} tomograms/{:s}\n".format(num + 1, rec))

            print("Converting particle positions and angles and writing .tbl file entry...")
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
                # Convert the Slicer angles to Dynamo Euler angles
                particle["angles"] = slicer_angles_to_dynamo_angles(particle["angles"])

                row = "{:d} 1 1 0 0 0 {:.3f} {:.3f} {:.3f} 0 0 0 1 {:d} {:d} 0 0 0 0 {:d} 0 0 0 {:.3f} {:.3f} {:.3f} 0 0 0 0 0 0\n".format(
                    global_particle_num, particle["angles"][0], particle["angles"][1], particle["angles"][2],
                    min_tilt, max_tilt, num + 1, particle["coords"][0], particle["coords"][1],
                    particle["coords"][2])

                table_file.write(row)
                global_particle_num += 1

        table_file.close()
        tomograms_doc_file.close()

    return "tomgrams_noctf_included.doc", "table_to_crop_notcf.tbl", "table_to_crop_notcf"


def dynamo_main(root, name, dynamo_args):

    # Generate .doc and .tbl files
    doc, tbl, basename = imod_processor_to_dynamo(root, name, dynamo_args)

    # Use template file to create Matlab script to run the remaining steps
    current_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    template = current_dir + "../../templates/dynamo/dynamo_process.m"
    template_path = os.path.realpath(template)
    processed_data_dir = root + "/processed_data"
    dynamo_root = processed_data_dir + "/Dynamo-from-IMOD"
    new_script = "%s/dynamo_process.py" % dynamo_root
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
                if re.match(r"^%% Process table", line):
                    break

                # If we are at an assignment line
                elif re.match(r".+ =", line):
                    line = line.strip()
                    tokens = line.split(" ")
                    variable_name = tokens[0]

                    value_to_write_out = ""
                    if variable_name == "basename":
                        value_to_write_out = f"\'{basename}\'"
                    elif variable_name == "doc_file":
                        value_to_write_out = f"\'{doc}\'"
                    elif variable_name == "tbl_file":
                        value_to_write_out = f"\'{tbl}\'"
                    elif variable_name == "particles_dir":
                        value_to_write_out = "\'particles\''"
                    elif variable_name in dynamo_args:
                        value_to_write_out = str(dynamo_args[variable_name])
                    else:
                        print("Missing Dynamo processing parameter: %s!" % variable_name)
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