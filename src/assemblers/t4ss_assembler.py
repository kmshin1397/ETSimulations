""" This module assembles fake membranous particles built to emulate the Type IV Secretion System

"""
# Built-in modules
import random
import os
from shutil import rmtree, copyfile
import logging
import math

# External packages
import numpy as np
from scipy.spatial.transform import Rotation as R

# Custom modules
from simulation.particle_set import ParticleSet
from simulation import chimera_server as Chimera

logger = logging.getLogger(__name__)

"""
    The classes below provide basic wrapper classes and functions for model 
    sub-structures for Type IV Secretion System simulations.
"""


class Barrel:
    """
    Basic class to assemble Chimera commands to open a "barrel" for a T4SS model

    Attributes:
        volume_id: The Chimera volume ID to assign to the opened barrel
        source: The path to the MRC to open for the barrel
        angle: Random angle relative to the membrane perpendicular assigned to the barrel.

    """

    def __init__(self, volume_id, source, angle, orig_coord_sys):
        self.volume_id = volume_id
        self.source = source
        self.angle = angle
        self.orig_coord_sys = orig_coord_sys

    def get_commands(self):
        """
        Get the list of commands to send to Chimera

        Returns: List of Chimera commands

        """
        commands = ["open #%d %s" % (self.volume_id, self.source),
                    "turn x %.3f models #%d center 0,0,0 coordinateSystem #%d" %
                    (self.angle[0], self.volume_id, self.orig_coord_sys),
                    "turn y %.3f models #%d center 0,0,0 coordinateSystem #%d" %
                    (self.angle[1], self.volume_id, self.orig_coord_sys)]
        return commands


# When assigning Volume ID, note that intermediate processes will use
# volume_id + 1 as well and thus assumes this Id value is still available,
# at least until volume creation of the rod is complete
class Rod:
    """
    Basic class to assemble Chimera commands to open a "rod" for a T4SS model

    Attributes:
        volume_id: The Chimera volume ID to assign to the opened rod
        source: The path to the MRC to open for the rod
        center: The location at which the rod should be centered
        degrees: The degrees to rotate the rod around the z-axis
        angle: Random angle relative to the membrane perpendicular assigned to the rod.
        orig_coord_sys: The reference model number for the original coordinate system for the entire
            particle - used in case the laboratory frame is changed by the user mid-assembly

    """

    def __init__(self, volume_id, source, center, degrees, angle, orig_coord_sys):
        self.volume_id = volume_id
        self.source = source
        self.center = center
        self.degrees = degrees
        self.angle = angle
        self.orig_coord_sys = orig_coord_sys

    def get_commands(self):
        """
        Get the list of commands to send to Chimera

        Returns: List of Chimera commands

        """
        center_string = "0,0,0"
        commands = ["open #%d %s" % (self.volume_id, self.source),
                    "turn z %.3f models #%d center 0,0,0 coordinateSystem #%d" % (self.degrees,
                                                                                  self.volume_id,
                                                                                  self.volume_id),
                    "move %.3f,%.3f,%.3f models #%d coordinateSystem #%d" % (self.center[0],
                                                                             self.center[1],
                                                                             self.center[2],
                                                                             self.volume_id,
                                                                             self.orig_coord_sys),
                    "turn x %.3f models #%d center %s coordinateSystem #%d" % (self.angle[0],
                                                                               self.volume_id,
                                                                               center_string,
                                                                               self.volume_id),
                    "turn y %.3f models #%d center %s coordinateSystem #%d" % (self.angle[1],
                                                                               self.volume_id,
                                                                               center_string,
                                                                               self.volume_id)]
        return commands


class T4SSAssembler:
    """ A custom particle Assembler class used to build up fake Type IV Secretion System particles

    Attributes:
        ### Attributes passed in on initialization ###
        model: The filepath to the particle source MRC which represents the T4SS
        temp_dir: The directory into which temporary truth volumes should be placed
        chimera_queue: The multiprocessing queue that the server process is listening to
        ack_event: The child process-specific acknowledgement event to subscribe to for
            completion notifications from the Chimera server
        pid: The ID of the child process running this assembler

        ### Other attributes ###
        commands: The list of Chimera commands accrued by the Assembler during processing, to be
            sent to the Chimera REST server once ready
        loaded_orientations: The entire distribution of potential orientations loaded in from a
            Dynamo tbl file
        chosen_orientations: The list of randomly selected particle orientations from the above
            distribution
        chosen_positions: The list of randomly selected displacements from the center of the
            membrane segment for each particle
        chosen_angles: The list of randomly selected angles off of the perpendicular to the
            membrane segment for each particle
        simulation: The src.simulation.tem_simulation.Simulation object responsible for feeding
            particles assembled here to a TEM-Simulator run

    """

    def __init__(self, model, temp_dir, chimera_queue, ack_event, pid, custom_args):
        """
        Initialize a new Assembler object

        """
        self.model = model
        self.temp_dir = temp_dir
        self.commands = []
        self.chimera_queue = chimera_queue

        # Event unique to each child process used to subscribe to a Chimera server command set
        # and listen for completion of commands request.
        self.ack_event = ack_event

        # Load in orientations distribution from file
        orientation_table = custom_args["orientations_tbl"]
        raw_data = np.loadtxt(orientation_table)
        self.loaded_orientations = raw_data[:, 6:9]

        self.chosen_orientations = []
        self.chosen_positions = []
        self.chosen_angles = []

        # An instance of the Simulation class that holds current iteration TEM-Simulator parameters
        self.simulation = None

        # The subprocess ID of the worker using this Assembler
        self.pid = pid

        self.custom_args = custom_args

    @staticmethod
    def __get_random_position():
        """
        Get a random shift from the center of the membrane segment to apply to a new particle

        Returns: A tuple (x, y) of the x-axis and y-axis shifts

        """
        x = random.randrange(-75, 75, 1)
        y = random.randrange(-75, 75, 1)
        return x, y

    @staticmethod
    def __get_random_angle():
        """
        Get a random angle away from the perpendicular to the membrane segment to apply to a new
        particle

        Returns: A random angle pair x,y from a Gaussian distribution of center 0 and standard
            deviation 5

        """
        return random.gauss(0, 5), random.gauss(0, 5)

    def __get_random_tbl_orientation(self):
        """
        Get a random particle orientation from the distribution loaded in from the .tbl file

        Returns: A tuple (Z, X, Z) of Euler angles randomly taken from the loaded distribution,
            inverted so that we have reference-to-particle angles

        """
        choice = random.choice(self.loaded_orientations).tolist()
        return [-choice[2], -choice[1], -choice[0]]

    def __open_membrane(self, model_id, particle_height_offset, orig_coord_sys):
        """
        Enqueues the command to open the previously saved membrane segment MRC to the Chimera
        session

        Args:
            model_id: The Chimera session model ID to assign to the opened membrane segment
            particle_height_offset: The z-axis offset to move up the membrane so that it sits above
                the particle
            orig_coord_sys: The reference model number for the original coordinate system for the
                entire particle - used in case the laboratory frame is changed by the user
                mid-assembly

        Returns: The model ID of the membrane volume within the Chimera segment

        """
        path = self.custom_args["membrane_path"]
        self.commands.append('open #%d %s' % (model_id + 10, path))
        self.commands.append(
            "vop scale #%d factor %0.3f modelId #%d" % (model_id + 10, 1.5, model_id))
        self.commands.append('close #%d' % (model_id + 10))
        return model_id

    def __assemble_particle(self, output_filename):
        """
        Assemble a new particle by putting together a membrane segment and a particle map at
        randomized angle/position/orientation

        Args:
            output_filename: The filepath where the assembled particle map is saved

        """
        # We create a small sphere to mark the original coordinate system reference for the Chimera
        # session. This will be used as an external reference to use to keep the following models
        # in a logical frame of reference while they are being moved and rotated
        reference_coord_sys = 999
        membrane_model = 98
        self.commands.append("shape sphere modelId #%d" % reference_coord_sys)

        # Clear state variables
        model_id = 1
        random_angles = []

        # Draw random orientation and position
        random_orientation = self.__get_random_tbl_orientation()

        # The random orientation gives proper side views from TEM-Simulator when viewed, but gives
        # the top-view in terms of the recorded rotations because source is top-view, so rotate it
        # by 90 around the X
        euler = [-random_orientation[2], -random_orientation[1], -random_orientation[0]]
        orientation = R.from_euler("zxz", euler, degrees=True)
        orientation_mat = np.dot(R.from_euler("zxz", [0, -90, 0], degrees=True).as_matrix(),
                                 orientation.as_matrix())
        corrected_orientation = R.from_matrix(orientation_mat).inv()
        corrected_orientation = corrected_orientation.as_euler("zxz", degrees=True).tolist()
        self.chosen_orientations.append(corrected_orientation)

        # Random position is with respect to center of membrane segment, not in entire tiltseries
        random_position = self.__get_random_position()
        self.chosen_positions.append(random_position)

        # Tack on membrane
        particle_height_offset = 18
        membrane_model = self.__open_membrane(membrane_model, particle_height_offset,
                                              reference_coord_sys)

        # Random angle with respect to the membrane (different from overall orientation angles)
        barrel_angle = self.__get_random_angle()
        random_angles.append(barrel_angle)
        b = Barrel(model_id, self.custom_args["barrel"], barrel_angle, membrane_model)
        self.commands.extend(b.get_commands())

        # Move the central barrel down to below the membrane
        self.commands.append(
            'move 0,0,%d models #%d coordinateSystem #%d' % (-particle_height_offset - 25,
                                                             b.volume_id,
                                                             membrane_model))
        # Rods
        rods_id = model_id + 1
        num_rods = self.custom_args["num_rods"]
        rod_ids = []
        for i in range(num_rods):
            deg_increment = 360. / num_rods
            degrees = deg_increment * i

            # Compute positions
            x = math.cos(math.radians(degrees)) * self.custom_args["rod_distance_from_center"]
            y = math.sin(math.radians(degrees)) * self.custom_args["rod_distance_from_center"]

            # Random angle with respect to the membrane (different from overall orientation angles)
            random_angle = self.__get_random_angle()

            # Note: rods seem to get added moved-down to where the barrel is automatically since the
            # last thing we added was the barrel, so no need to move them down with a command
            rod = Rod(rods_id + i, self.custom_args["rod"], (x, y, 0), degrees, random_angle,
                      membrane_model)
            rod_ids.append(rods_id + i)
            random_angles.append(random_angle)

            self.commands.extend(rod.get_commands())

        self.chosen_angles.append(random_angles)

        # Combine the barrel and rod maps
        full_model = 99
        max_rod_id = rod_ids[-1]
        combine_command = "vop add #%d-%d modelId #%d" % (model_id, max_rod_id, full_model)
        self.commands.append(combine_command)

        # Apply random position
        self.commands.append("move %.2f,%.2f,0 models #%d coordinateSystem #%d" %
                             (random_position[0], random_position[1], full_model, membrane_model))

        # Commands to combine membrane and particle into one mrc
        final_model = 100
        self.commands.append(
            "vop add #%d-%d modelId #%d" % (membrane_model, full_model, final_model))

        self.commands.append(
            "vop scale #%d factor %0.3f modelId #%d" % (final_model, 3, final_model + 1))
        self.commands.append(
            "vop scale #%d shift %0.3f modelId #%d" % (final_model, 4.875, final_model + 2))

        # Save truth particle map
        self.commands.append("volume #%d save %s" % (final_model + 2, output_filename))

        # Clear for the next particle
        self.commands.append("close session")

        return random_orientation, random_position, random_angles, corrected_orientation

    def __send_commands_to_chimera(self):
        """
        Send the accumulated Chimera commands to the Chimera server for completion, waiting until
        the commands have been carried out

        """
        command_set = Chimera.ChimeraCommandSet(self.commands, self.pid, self.ack_event)
        command_set.send_and_wait(self.chimera_queue)

        # Clear ack event for future commands
        self.ack_event.clear()

    def set_up_tiltseries(self, simulation):
        """
        Assembles a set of new particles to be placed in a single simulated tilt stack, and updates
        the TEM-Simulator configurations accordingly

        For number of particles (i.e 4):
            1. Make a temp truth volume
            2. Assemble particle and save truth
            3. Set up sim configs and update TEM input files

        Args:
            simulation: The src.simulation.tem_simulation.Simulation object responsible for feeding
                particles assembled here to a TEM-Simulator run, passed in from the simulation child
                process running the simulation using this Assembler.

        """
        self.simulation = simulation
        self.commands = []

        # Get particle coordinates from base file provided
        num_particles = self.simulation.get_num_particles()
        coordinates = self.simulation.parse_coordinates()

        truth_vols_dir = self.temp_dir + "/truth_vols"
        os.mkdir(truth_vols_dir)

        custom_metadata = {"shifts_from_membrane_center": [],
                           "angles_from_membrane_perpendicular": [],
                           "true_orientations": []}

        particle_sets = []
        for i in range(num_particles):
            # We use a new particle "set" per particle, since each will come from a slightly
            # different source map (based on randomized angles/position with respect to the
            # membrane)
            particle_set = ParticleSet("T4SS%d" % (i + 1), key=True)

            new_particle = truth_vols_dir + "/%d.mrc" % i

            # Assemble a new particle
            true_orientation, position, angles, side_view_orientation = self.__assemble_particle(new_particle)

            # If we want to add noise to orientations, do it here
            if "orientations_error" in self.custom_args:
                error_params = self.custom_args["orientations_error"]
                mu = error_params["mu"]
                sigma = error_params["sigma"]

                # Record the error parameters used
                custom_metadata["orientations_error_distribution"] = \
                    "gauss({:f}, {:f})".format(mu, sigma)
                noise_z1, noise_x, noise_z2 = (random.gauss(mu, sigma), random.gauss(mu, sigma),
                                               random.gauss(mu, sigma))
                # Save a noisy, side-view orientation
                noisy_orientation = [side_view_orientation[0] + noise_z1,
                                     side_view_orientation[1] + noise_x,
                                     side_view_orientation[2] + noise_z2]

                # Update metadata records for changed orientations
                custom_metadata["true_orientations"].append(true_orientation)

                # Pass along to TEM-Simulator the noisy top-view orientation, but record the side view
                particle_set.add_orientation_to_simulate(true_orientation, noisy_version=noisy_orientation)
            else:
                # Pass along to TEM-Simulator the true top-view orientation, but record the side view
                particle_set.add_orientation_to_simulate(true_orientation)
                particle_set.add_orientation_to_save(side_view_orientation)

            # Update the other simulation parameters with the new particle
            particle_set.add_coordinate(coordinates[i])
            particle_set.add_source(new_particle)
            particle_set.num_particles += 1

            custom_metadata["shifts_from_membrane_center"].append(position)
            custom_metadata["angles_from_membrane_perpendicular"].append(angles)

            particle_sets.append(particle_set)

        # Make all four particles atomically, so that other threads can make their own while we move
        # on to the TEM-Simulator step
        self.__send_commands_to_chimera()

        # Apply completed particle set to TEM-Simulator configs
        self.simulation.create_particle_lists(particle_sets)

        self.simulation.set_custom_data(custom_metadata)

    def reset_temp_dir(self):
        """
        Cleans up the temporary files directory used by the Assembler (can be used to set up for a
        new TEM-Simulator run without having to re-instantiate the Assembler)

        """
        rmtree(self.temp_dir + "/truth_vols")

    def close(self):
        """
        Let the Chimera server know that this Assembler is done using the server

        """
        self.commands = ["END"]
        self.__send_commands_to_chimera()
