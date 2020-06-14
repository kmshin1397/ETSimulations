""" This module implements the processing function for the I3 software package.

The module will create an I3 project directory.
"""

import os
import struct
import shutil
import mrcfile
import numpy as np


def get_mrc_size(rec):
    """
    Return the half the size of each dimension for an MRC file, so that we can move the origin to
        the center instead of the corner of the file

    Args:
        rec: the MRC file to get the size of

    Returns: A tuple (x/2, y/2, z/2) of the half-lengths in each dimension

    """
    with mrcfile.open(rec) as mrc:
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

    Args:
        angles:

    Returns:

    """

    # Slicer stores angles in XYZ order even though rotations are applied as ZYX, so we flip here
    rot = R.from_euler('zyx', [angles[2], angles[1], angles[0]], degrees=True)
    # The Slicer angles are particle-to-reference, but PEET MOTLs are ref-to-part, so we invert
    rot = rot.inv()
    # motl = rot.as_euler('zxz', degrees=True)
    # print(motl)
    # rot = R.from_euler('zxz', [motl[0], motl[1], motl[2]], degrees=True)
    matrix = rot.as_matrix()
    return matrix


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
                    (rot_matrix[0][0], rot_matrix[0][1], rot_matrix[0][2],
                     rot_matrix[1][0], rot_matrix[1][1], rot_matrix[1][2],
                     rot_matrix[2][0], rot_matrix[2][1], rot_matrix[2][2])

        lines.append(new_line)

    return lines


def get_simulated_particle_info():
    pass


def imod_processor_to_i3(root, i3_args):
    """
    Implements the I3 processing of simulated data that was reconstructed using the IMOD Processor.

    Args:
        root: The ETSimulations project root directory
        i3_args: The I3 Processor arguments

    Returns: None

    """

    # -------------------------------------
    # Set up I3 project directory structure
    # -------------------------------------
    print("Creating I3 project directories")
    processed_data_dir = root + "/processed_data"
    i3_root = processed_data_dir + "/I3"
    imod_dir = processed_data_dir + "/IMOD"
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
    for subdir in os.listdir(imod_dir):
        if subdir.startswith(i3_args["dir_pattern"]):

            print("Collecting information for directory: %s" % subdir)

            # Look for the necessary IMOD files
            mod = ""
            tlt = ""
            rec = ""
            for file in os.listdir(os.path.join(imod_dir, subdir)):
                if i3_args["mod_pattern"] in file and file.endswith(".mod"):
                    mod = file
                elif i3_args["tlt_pattern"] in file and file.endswith(".tlt"):
                    tlt = file
                elif i3_args["rec_pattern"] in file and (file.endswith(".mrc") or
                                                         file.endswith(".rec")):
                    rec = file

                # Break out of loop once all three relevant files have been found
                if mod != "" and tlt != "" and rec != "":
                    break

            basename = os.path.splitext(rec)[0]

            # Copy over the tomogram to the maps folder
            if rec != "":
                shutil.copyfile(os.path.join(imod_dir, subdir, rec), os.path.join(maps_path, rec))
            else:
                print("ERROR: No reconstruction was found for sub-directory: %s" % subdir)
                exit(1)

            # Copy over the tlt file to the maps folder
            if tlt != "":
                shutil.copyfile(os.path.join(imod_dir, subdir, tlt), os.path.join(maps_path, tlt))
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
            new_sets_line = "%s %s_%s\n" % (rec, basename, i3_args["particle_name"])
            sets_file.write(new_sets_line)

            # Read the .mod file info
            print("Reading the .mod file for Slicer info...")
            slicer_info = get_slicer_info(os.path.join(imod_dir, subdir, mod))
            print("Shifting the origins to the center for the particle coordinates...")
            rec_fullpath = os.path.join(imod_dir, subdir, rec)
            size = get_mrc_size(rec_fullpath)
            for particle in slicer_info:
                # Shift the coordinates to have the origin at the tomogram center
                particle["coords"] = center_coordinates(particle["coords"], size)

            # Write the trf file for this tomogram
            print("Writing the .trf file...")
            trf_filepath = os.path.join(trf_path, "%s.trf" % basename)
            with open(trf_filepath, 'w') as trf:
                lines = get_trf_lines(slicer_info, basename)
                trf.writelines(lines)

    # Close files
    maps_file.close()
    sets_file.close()


def i3_main(root, name, i3_args):
    root = i3_args["imod_dir"]

    # -------------------------------------
    # Set up I3 project directory structure
    # -------------------------------------
    print("Creating I3 project directories")
    processed_data_dir = root + "/processed_data"
    i3_root = processed_data_dir + "/I3"
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
                shutil.copyfile(os.path.join(root, subdir, tlt), os.path.join(maps_path, tlt))
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
            new_sets_line = "%s %s_%s\n" % (rec, basename, i3_args["particle_name"])
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
            trf_filepath = os.path.join(trf_path, "%s.trf" % basename)
            with open(trf_filepath, 'w') as trf:
                lines = get_trf_lines(slicer_info, basename)
                trf.writelines(lines)

    # Close files
    maps_file.close()
    sets_file.close()
