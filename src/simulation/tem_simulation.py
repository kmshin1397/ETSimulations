""" This module holds the Simulation class, which represents the configurations and metadata
associated with a single run of the TEM-Simulator.

"""

import os
from shutil import move
from tempfile import mkstemp
import re
from subprocess import check_output
import random
import logging

logger = logging.getLogger(__name__)


class Simulation:
    """A class to hold associated configurations and metadata for a run of the TEM-Simulator.

    Attributes:
        ### Attributes passed in on initialization ###
        config_file: The file path to the TEM-Simulation configuration input file
        base_coord_file: The file path to the TEM-Simulator particle coordinates file to use as
            base orientations/locations
        tiltseries_file: The output tiltseries file path
        nonoise_tilts_file: The no-noise version of the output tiltseries file path
        global_stack_no: The ID number of this simulated stack within the experiment
        temp_dir: The directory to use to store temporary input files
        apix: (optional) the APIX value to provide to the TEM-Simulator if a PDB source is used

        ### Other attributes ###
        orientations: The orientations given to the particles of interest
        positions: The positions given to the particles of interest
        sim_log_file: The file path to use for the temporary TEM-Simulator log file
        custom_data: Field that can be used to store custom Assembler-specific metadata which will
            be output to the metadata log

    """

    def __init__(
        self,
        config_file,
        base_coord_file,
        tiltseries_file,
        nonoise_tilts_file,
        global_stack_no,
        temp_dir,
        apix=None,
        defocus=5,
        template_configs="",
        template_coords="",
        coord_error=None,
    ):
        # TEM-Simulator configuration input file
        self.config_file = config_file

        # TEM-Simulator particle coordinates file to use as base orientations/locations
        self.base_coord_file = base_coord_file

        # An error distribution to apply to particle coordinates, if desired
        self.coord_error = coord_error

        # Orientations given to the particles of interest
        self.orientations = []

        # Positions given to the particles of interest
        self.positions = []

        # The output tiltseries file
        self.tiltseries_file = tiltseries_file

        # The no-noise version output file
        self.nonoise_tilts_file = nonoise_tilts_file

        # The ID number of this stack within the experiment
        self.global_stack_no = global_stack_no

        # Where to use for temporary input files
        self.temp_dir = temp_dir

        # Place to put temporary TEM-Simulator log file
        self.sim_log_file = temp_dir + "/simulator.log"

        # Field to store Assembler-specific metadata.
        self.custom_data = None

        # If the model being used is a PDB, we must provide an apix value
        self.apix = apix

        # The defocus value to use for the simulation
        self.defocus = defocus

        # The original template TEM-Simulator configuration files, for the log records
        self.template_configs = template_configs
        self.template_coords = template_coords

    def extend_positions(self, positions):
        """
        Extend the positions attribute with a given list of positions

        Args:
            positions: A list of positions (X, Y, Z) to extend the positions list by

        """
        self.positions.extend(positions)

    def add_orientation(self, orientation):
        """
        Append to the orientations attribute

        Args:
            orientation: The intrinsic Euler angles (z1, x, z2) to append to the orientations list

        """
        self.orientations.append(orientation)

    def extend_orientations(self, orientations):
        """
        Extend the orientations attribute with a given list of orientations

        Args:
            orientations: A list of extrinsic Euler angles (z1, x, z2) to extend the orientations
                list by

        """
        self.orientations.extend(orientations)

    def set_custom_data(self, data):
        """
        Update the custom data field, which is directly recorded in the metadata logs. Can be used
        to keep track of information specific to custom Assemblers

        Args:
            data: The data object that should be recorded in the metadata logs

        """
        self.custom_data = data

    def get_metadata(self):
        """
        Get the important contents of the Simulation object in dictionary form (the non-temp files)

        Returns: The attributes of the Simulation object in dictionary form, to be used as metadata
            logging

        """
        metadata = {
            "output": self.tiltseries_file,
            "nonoise_output": self.nonoise_tilts_file,
            "global_stack_no": self.global_stack_no,
            "apix": self.apix,
            "defocus": self.defocus,
            "sim_configs": self.template_configs,
            "particle_coords": self.template_coords,
            "orientations": self.orientations,
            "positions": self.positions,
            "custom_data": self.custom_data,
        }

        if self.coord_error is not None:
            mu = self.coord_error["mu"]
            sigma = self.coord_error["sigma"]
            metadata["coord_error"] = "gauss({:f}, {:f})".format(mu, sigma)

        return metadata

    # Replace line in file with a new line
    @staticmethod
    def __replace(file_path, pattern, subst):
        """
        Helper function to go through a text file and replace instances of a given pattern with the
            provided replacement

        Args:
            file_path: The text file to make the replacement in
            pattern: The pattern to look to replace within the text file
            subst: The string to substitute in for instances of the pattern

        """
        # Create temp file
        fh, abs_path = mkstemp()
        with os.fdopen(fh, "w") as new_file:
            with open(file_path) as old_file:
                for line in old_file:
                    new_line = re.sub(pattern, subst, line)
                    new_file.write(new_line)

        # Remove original file
        os.remove(file_path)
        # Move new file
        move(abs_path, file_path)

    @staticmethod
    def __replace_nonoise(file_path, pattern, subst):
        """
        Variant helper function of the __replace function used to replace the no-noise tiltseries
            file path in the configs file, since it replaces just the second instance of the given
            pattern

        Args:
            file_path: The text file to make the replacement in
            pattern: The pattern to look for and replace the second instance of within the file
            subst: The string to substitute in for the second instance of the pattern

        """
        # Create temp file
        fh, abs_path = mkstemp()
        found_first = False
        replaced = False
        with os.fdopen(fh, "w") as new_file:
            with open(file_path) as old_file:
                for line in old_file:
                    if replaced:
                        new_file.write(line)
                    elif found_first and re.match(pattern, line) is not None:
                        new_line = re.sub(pattern, subst, line)
                        new_file.write(new_line)
                        replaced = True
                    else:
                        if re.match(pattern, line) is not None:
                            found_first = True
                        new_file.write(line)

        # Remove original file
        os.remove(file_path)
        # Move new file
        move(abs_path, file_path)

    def edit_output_files(self):
        """
        Go into the actual TEM-Simulator input files and update the output and log file values to
            be what is currently stored in the appropriate class attributes
        """
        image_file_out_pattern = "^image_file_out = .*\n"
        replacement_line = "image_file_out = %s\n" % self.tiltseries_file
        self.__replace(self.config_file, image_file_out_pattern, replacement_line)

        replacement_line = "image_file_out = %s\n" % self.nonoise_tilts_file
        self.__replace_nonoise(
            self.config_file, image_file_out_pattern, replacement_line
        )

        log_pattern = "^log_file = .*\n"
        replacement_line = "log_file = %s\n" % self.sim_log_file
        self.__replace(self.config_file, log_pattern, replacement_line)

        defocus_pattern = "^defocus_nominal = .*\n"
        replacement_line = "defocus_nominal = %.3f\n" % self.defocus
        self.__replace(self.config_file, defocus_pattern, replacement_line)

    def get_num_particles(self):
        """
        Open the self.base_coord_file and get the number of particles for the simulation indicated

        Returns: The number of particles indicated by the coordinates file

        """
        with open(self.base_coord_file, "r") as f:
            for line in f.readlines():
                if line.startswith("#"):  # Ignore comment lines
                    continue
                else:
                    num_particles = int(line.strip().split()[0])
                    return num_particles

    def __convert_coordinates(self, coordinates):
        """
        Give particle coordinates provided in pixels, convert them to nanometers.

        Returns: A list of lists [x, y, z] representing particle positions in nm.
        """
        for i, point in enumerate(coordinates):
            coordinates[i] = map(lambda x: x * self.apix * 0.1, point)

        return coordinates

    def parse_coordinates(self):
        """
        Read the particle coordinates in self.base_coord_file and return them as an array

        Returns: A list of lists [x, y, z] representing particle positions

        """
        coordinates = []
        with open(self.base_coord_file, "r") as f:
            read_summary_line = False
            for line in f.readlines():
                if line.startswith("#"):  # Ignore comment lines
                    continue
                else:
                    if not read_summary_line:
                        read_summary_line = True
                    else:
                        tokens = line.strip().split()
                        coordinate = [
                            float(tokens[0]),
                            float(tokens[1]),
                            float(tokens[2]),
                        ]
                        coordinates.append(coordinate)

        if self.coord_error is not None:
            mu = self.coord_error["mu"]
            sigma = self.coord_error["sigma"]

            noisy_coordinates = []
            for coordinate in coordinates:
                noisy_coordinates.append(
                    [
                        coordinate[0] + random.gauss(mu, sigma),
                        coordinate[1] + random.gauss(mu, sigma),
                        coordinate[2] + random.gauss(mu, sigma),
                    ]
                )

            coordinates = noisy_coordinates

        return self.__convert_coordinates(coordinates)

    @staticmethod
    def __write_coord_file(filename, coordinates, orientations):
        """
        Helper function to write out particle coordinates and orientations in the format expected
            by TEM-Simulator for a particle set

        Args:
            filename: The coordinates file to write out a particle set's information to
            coordinates: The list of particle coordinates to write out
            orientations: The list of particle Euler angles (extrinsic ZXZ) to write out

        """
        with open(filename, "w") as f:
            f.write("%d 6\n" % len(coordinates))
            for i, coordinate in enumerate(coordinates):
                orientation = orientations[i]
                new_line = "%d %d %d %d %d %d\n" % (
                    coordinate[0],
                    coordinate[1],
                    coordinate[2],
                    orientation[0],
                    orientation[1],
                    orientation[2],
                )
                f.write(new_line)

    def __write_particle_section(self, particle_name, source, voxel_size=0.283):
        """
        For a given particle set, write out the particle parameters segment for the TEM-Simulator
            configuration file

        Args:
            particle_name: The particle name assigned to this set
            source: The source MRC or PDB file used to simulate the particle from
            voxel_size: If passing a PDB source, a voxel size (apix, in nm) must be provided

        """
        with open(self.config_file, "a") as f:
            f.write("=== particle %s ===\n" % particle_name)

            if source.endswith(".mrc"):
                f.write("source = map\n")
                f.write("map_file_re_in = %s\n" % source)
                f.write("use_imag_pot = no\n")
                f.write("famp = 0\n\n")

            elif source.endswith(".pdb"):
                f.write("source = pdb\n")
                f.write("pdb_file_in = %s\n" % source)
                f.write("voxel_size = %0.3f\n\n" % voxel_size)

    def __write_particle_set_section(self, particle_set, coord_file):
        """
        For a given particle set, write out the "particleset" parameters segment for the
            TEM-Simulator configuration file

        For more information on what a particle set is, refer to the TEM-Simulator manual.

        Args:
            particle_set: The src.particle_set.ParticleSet object containing various particle set
                parameters
            coord_file: The TEM-Simulator coordinates file to write out parameters to

        """
        with open(self.config_file, "a") as f:
            f.write("=== particleset ===\n")
            f.write("particle_type = %s\n" % particle_set.name)
            f.write("num_particles = %d\n" % particle_set.num_particles)
            f.write("particle_coords = file\n")
            f.write("coord_file_in = %s\n\n" % coord_file)

    def __write_fiducials_particle_set_section(self, bead_occupancy):
        """
        Write out the "particleset" section for the gold fiducials, which uses the random
            coordinates from the occupancy option for the TEM-simulator instead of the standard
            coordinates text files.

        """
        with open(self.config_file, "a") as f:
            f.write("=== particleset ===\n")
            f.write("particle_type = Fiducial\n")
            f.write("occupancy = %f\n" % bead_occupancy)
            f.write("particle_coords = random\n")
            f.write("where = volume\n\n")

    def create_particle_lists(self, particle_sets):
        """
        Read the particle coordinates in self.base_coord_file and return them as an array

        Args:
            particle_sets: A list of src.particle_set.ParticleSet objects holding parameters to
                update TEM-Simulator configuration files with

        """
        for particle_set in particle_sets:
            particle = particle_set.name

            # Create a coordinates file for this set
            new_coord_file = "%s/%s_coord.txt" % (self.temp_dir, particle)

            # If this is the main particle in the tilt stack, update simulation metadata
            if particle_set.key:
                # Record (for metadata) noisy versions of the orientations if they exist, otherwise
                # the true ones
                if particle_set.noisy_orientations:
                    self.extend_orientations(particle_set.noisy_orientations)
                else:
                    self.extend_orientations(particle_set.orientations_to_save)

                self.extend_positions(particle_set.coordinates)

            self.__write_coord_file(
                new_coord_file,
                particle_set.coordinates,
                particle_set.orientations_to_simulate,
            )

            # Add Particle and ParticleSet segments to config file
            self.__write_particle_section(particle, particle_set.source, self.apix)
            self.__write_particle_set_section(particle_set, new_coord_file)

    def create_fiducials(self, fiducials_source, bead_occupancy):
        """
        Set up the TEM-simulator configurations to generate randomly distributed gold fiducials

        Args:
            fiducials_source: The MRC file designed to simulate gold fiducials
            bead_occupancy: The TEM-Simulator occupancy value for the beads

        """

        # Add Particle and ParticleSet segments to config file
        self.__write_particle_section("Fiducial", fiducials_source, self.apix)
        self.__write_fiducials_particle_set_section(bead_occupancy)

    def run_tem_simulator(self, tem_exec_path):
        """
        Given the executable path to the TEM-Simulator, run the simulation with the set-up
            specified by current Simulation object attributes

        Args:
            tem_exec_path: The full path to the executable for the TEM-Simulator software

        """
        logger.info("Running TEM-Simulator")

        # Need to provide executable path because subprocess does not know about aliases
        # TEM_exec_path = '/home/kshin/Documents/software/TEM-simulator_1.3/src/TEM-simulator'
        command = tem_exec_path + " " + self.config_file
        check_output(command.split())
        logger.info("TEM-Simulator finished running")

    def close(self):
        logger.debug("Closing Simulator instance")
