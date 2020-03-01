""" This module assembles fake membranous particles built to emulate the Type IV Secretion System

"""
# Built-in modules
import random
import os
from shutil import rmtree
import logging

# External packages
import numpy as np

# Custom modules
from simulation.particle_set import ParticleSet
from simulation import chimera_server as Chimera

logger = logging.getLogger(__name__)


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
        simulation: The src.simulation.Simulation object responsible for feeding particles assembled
            here to a TEM-Simulator run

    Methods:
        ### Private methods ###
        __get_random_position: Get a random shift from the center of the membrane segment to apply
            to a new particle
        __get_random_angle: Get a random article away from the perpendicular to the membrane segment
            to apply to a new particle
        __get_random_tbl_orientation: Get a random particle orientation from the distribution
            loaded in from the .tbl file
        __open_membrane: Enqueues the command to open the previously saved membrane segment MRC to
            the Chimera session
        __assemble_particle: Assemble a new particle by putting together a membrane segment and a
            particle map at randomized angle/position
        __send_commands_to_chimera: Send the accumulated Chimera commands to the Chimera server for
            completion, waiting until the commands have been carried out

        ### Public methods ###
        set_up_tiltseries: Assembles a set of new particles to be placed in a single simulated tilt
            stack, and updates the TEM-Simulator configurations accordingly
        reset_temp_dir: Cleans up the temporary files directory used by the Assembler (can be used
            to set up for a new TEM-Simulator run without having to re-instantiate the Assembler)
        close: Sends a notification to the Chimera REST server that this particular Assembler (and
            thus the child process using the Assembler, as currently set up) is done using the
            Chimera server

    """
    def __init__(self, model, temp_dir, chimera_queue, ack_event, pid):
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
        # orientation_table = "/data/kshin/T4SS_sim/manual_full.tbl"
        orientation_table = \
            "/Users/kshin/Documents/data/T4SS/simulations/parallel_test/manual_full.tbl"
        raw_data = np.loadtxt(orientation_table)
        self.loaded_orientations = raw_data[:, 6:9]

        self.chosen_orientations = []
        self.chosen_positions = []
        self.chosen_angles = []

        # An instance of the Simulation class that holds current iteration TEM-Simulator parameters
        self.simulation = None

        # The subprocess ID of the worker using this Assembler
        self.pid = pid

    @staticmethod
    def __get_random_position():
        """
        Get a random shift from the center of the membrane segment to apply to a new particle

        Returns: A tuple (x, y) of the x-axis and y-axis shifts

        """
        x = random.randrange(-125, 125, 1)
        y = random.randrange(-125, 125, 1)
        return x, y

    @staticmethod
    def __get_random_angle():
        """
        Get a random article away from the perpendicular to the membrane segment to apply to a new
        particle

        Returns: A random angle from a Gaussian distribution of center 0 and standard deviation 5

        """
        return random.gauss(0, 5)

    def __get_random_tbl_orientation(self):
        """
        Get a random particle orientation from the distribution loaded in from the .tbl file

        Returns: A tuple (Z, X, Z) of Euler angles randomly taken from the loaded distribution,
            inverted so that we have particle-to-reference angles

        TODO: Check that the tbl actually has reference-to-particle rotations
        """
        choice = random.choice(self.loaded_orientations).tolist()
        return [-choice[2], -choice[1], -choice[0]]

    def __open_membrane(self, model_id, particle_height_offset):
        """
        Enqueues the command to open the previously saved membrane segment MRC to the Chimera
        session

        Args:
            model_id: The Chimera session model ID to assign to the opened membrane segment
            particle_height_offset: The z-axis offset to move up the membrane so that it sits above
                the particle

        Returns: The model ID of the membrane volume within the Chimera segment

        """
        # path = "/data/kshin/T4SS_sim/mem_large.mrc"
        path = "/Users/kshin/Documents/data/T4SS/simulations/parallel_test/mem_large.mrc"
        self.commands.append('open #%d %s' % (model_id, path))
        self.commands.append('move 0,0,%d models #%d' % (particle_height_offset + 25, model_id))
        return model_id

    def __assemble_particle(self, output_filename):
        """
        Assemble a new particle by putting together a membrane segment and a particle map at
        randomized angle/position/orientation

        Args:
            output_filename: The filepath where the assembled particle map is saved

        """

        # Clear state variables
        model_id = 0

        # Draw random orientation and position
        random_orientation = self.__get_random_tbl_orientation()
        self.chosen_orientations.append(random_orientation)

        # Random position is with respect to center of membrane segment, not in entire tiltseries
        random_position = self.__get_random_position()
        self.chosen_positions.append(random_position)

        model = Chimera.load_model_from_source(self.model, model_id, self.commands)

        # Tack on membrane
        particle_height_offset = 75
        membrane_model = self.__open_membrane(100, particle_height_offset)

        # Apply random position
        self.commands.append("move %.2f,%.2f,0 models #%d" % (random_position[0],
                                                              random_position[1], model))

        # Apply random angle with respect to the membrane
        random_angle = self.__get_random_angle()
        self.chosen_angles.append(random_angle)
        self.commands.append("turn y %.2f models #%d" % (random_angle, model))

        # Commands to combine membrane and particle into one mrc
        final_model = 99
        self.commands.append("vop add #%d,#%d modelId #%d" % (membrane_model, model, final_model))

        # Save truth particle map
        self.commands.append("volume #%d save %s" % (final_model, output_filename))

        # Clear for the next particle
        self.commands.append("close session")

        return random_orientation, random_position, random_angle

    def __send_commands_to_chimera(self):
        """
        Send the accumulated Chimera commands to the Chimera server for completion, waiting until
        the commands have been carried out

        """
        command_set = Chimera.ChimeraCommandSet(self.commands, self.pid, self.ack_event)
        command_set.send_and_wait(self.chimera_queue)

    def set_up_tiltseries(self, simulation):
        """
        Assembles a set of new particles to be placed in a single simulated tilt stack, and updates
        the TEM-Simulator configurations accordingly

        For number of particles (i.e 4)
            Make a temp truth volume
            Assemble particle and save truth
            Set up sim configs and update TEM input files

        Args:
            simulation: The src.simulation.Simulation object which holds the relevant TEM-Simulator
                run parameters

        """
        self.simulation = simulation

        # Get particle coordinates from base file provided
        num_particles = self.simulation.get_num_particles()
        coordinates = self.simulation.parse_coordinates()

        truth_vols_dir = self.temp_dir + "/truth_vols"
        os.mkdir(truth_vols_dir)

        custom_metadata = {"shifts_from_membrane_center": [],
                           "angles_from_membrane_perpendicular": []}

        particle_sets = []
        for i in range(num_particles):
            # We use a new particle "set" per particle, since each will come from a slightly
            # different source map (based on randomized angles/position with respect to the
            # membrane)
            particle_set = ParticleSet("T4SS%d" % (i + 1), key=True)

            new_particle = truth_vols_dir + "/%d.mrc" % i

            # Assemble a new particle
            orientation, position, angle = self.__assemble_particle(new_particle)

            # Update the simulation parameters with the new particle
            particle_set.add_orientation(orientation)
            particle_set.add_coordinate(coordinates[i])
            particle_set.add_source(new_particle)
            particle_set.num_particles += 1

            custom_metadata["shifts_from_membrane_center"].append(position)
            custom_metadata["angles_from_membrane_perpendicular"].append(angle)

            particle_sets.append(particle_set)

        # Make all four particles atomically, so that other threads can make their own while we move
        # on to the TEM-Simulator step
        self.__send_commands_to_chimera()

        # Apply completed particle set to TEM-Simulator configs
        self.simulation.create_particle_lists(particle_sets)

        self.simulation.custom_data = custom_metadata

        return self.simulation

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
