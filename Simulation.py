import sys
import os
from shutil import move
from tempfile import mkstemp
import re
from subprocess import check_output
import logging

logger = logging.getLogger(__name__)


class Simulation:

    def __init__(self, config_file, base_coord_file, tiltseries_file, nonoise_tilts_file,
                 global_stack_no, temp_dir):
        # TEM-Simulator configuration input file
        self.config_file = config_file

        # TEM-Simulator particle coordinates file to use as base orientations/locations
        self.base_coord_file = base_coord_file

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

    def add_position(self, position):
        self.positions.append(position)

    def extend_positions(self, positions):
        self.positions.extend(positions)

    def add_orientation(self, orientation):
        self.orientations.append(orientation)

    def extend_orientations(self, orientations):
        self.orientations.extend(orientations)

    def get_metadata(self):
        return self.__dict__

    # Replace line in file with a new line
    @staticmethod
    def __replace(file_path, pattern, subst):
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

    @staticmethod
    def __replace_nonoise(file_path, pattern, subst):
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

    def edit_output_files(self):
        image_file_out_pattern = "^image_file_out = .*\n"
        replacement_line = "image_file_out = %s\n" % self.tiltseries_file
        self.__replace(self.config_file, image_file_out_pattern, replacement_line)

        replacement_line = "image_file_out = %s\n" % self.nonoise_tilts_file
        self.__replace_nonoise(self.config_file, image_file_out_pattern, replacement_line)

        log_pattern = "^log_file = .*\n"
        replacement_line = "log_file = %s\n" % self.sim_log_file
        self.__replace(self.config_file, log_pattern, replacement_line)

    def get_num_particles(self):
        with open(self.base_coord_file, 'r') as f:
            for line in f.readlines():
                if line.startswith("#"):  # Ignore comment lines
                    continue
                else:
                    num_particles = int(line.strip().split()[0])
                    return num_particles

    def parse_coordinates(self):
        coordinates = []
        with open(self.base_coord_file, 'r') as f:
            read_summary_line = False
            for line in f.readlines():
                if line.startswith("#"):  # Ignore comment lines
                    continue
                else:
                    if not read_summary_line:
                        read_summary_line = True
                    else:
                        tokens = line.strip().split()
                        coordinate = (float(tokens[0]), float(tokens[1]), float(tokens[2]))
                        coordinates.append(coordinate)

        return coordinates

    @staticmethod
    def __write_coord_file(filename, coordinates, orientations):
        with open(filename, 'w') as f:
            f.write("%d 6\n" % len(coordinates))
            for i, coordinate in enumerate(coordinates):
                orientation = orientations[i]
                new_line = "%d %d %d %d %d %d\n" % (coordinate[0], coordinate[1], coordinate[2],
                                                    orientation[0], orientation[1], orientation[2])
                f.write(new_line)

    def __write_particle_section(self, particle_name, source, voxel_size=0.1):
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
                f.write("voxel_size = %0.2f\n\n" % voxel_size)

    def __write_particle_set_section(self, particle_set, coord_file):
        with open(self.config_file, "a") as f:
            f.write("=== particleset ===\n")
            f.write("particle_type = %s\n" % particle_set.name)
            f.write("num_particles = %d\n" % particle_set.num_particles)
            f.write("particle_coords = file\n")
            f.write("coord_file_in = %s\n\n" % coord_file)

    def create_particle_lists(self, particle_sets):
        for particle_set in particle_sets:
            particle = particle_set.name

            # Create a coordinates file for this set
            new_coord_file = "%s/%s_coord.txt" % (self.temp_dir, particle)

            # If this is the main particle in the tilt stack, update simulation metadata
            if particle_set.key:
                self.extend_orientations(particle_set.orientations)
                self.extend_positions(particle_set.coordinates)

            self.__write_coord_file(new_coord_file, particle_set.coordinates,
                                    particle_set.orientations)

            # Add Particle and ParticleSet segments to config file
            self.__write_particle_section(particle, particle_set.source)
            self.__write_particle_set_section(particle_set, new_coord_file)

    def run_tem_simulator(self):
        logger.info("Running TEM-Simulator")

        # Need to provide executable path because subprocess does not know about aliases
        # TEM_exec_path = '/home/kshin/Documents/software/TEM-simulator_1.3/src/TEM-simulator'
        TEM_exec_path = "/Users/kshin/Documents/software/TEM-simulator_1.3/src/TEM-simulator"
        command = TEM_exec_path + " " + self.config_file
        check_output(command.split()).decode(sys.stdout.encoding)
        logger.info("TEM-Simulator finished running")
