# Built-in modules
import random
import os
from shutil import rmtree

# External packages
import numpy as np

# Custom modules
from ParticleSet import ParticleSet
import ChimeraServer as Chimera


class T4SSAssembler:
    def __init__(self, model, temp_dir, chimera_queue, ack_event, pid):
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
        x = random.randrange(-125, 125, 1)
        y = random.randrange(-125, 125, 1)
        return x, y

    @staticmethod
    def __get_random_angle():
        return random.gauss(0, 5)

    def __get_random_tbl_orientation(self):
        choice = random.choice(self.loaded_orientations).tolist()
        return [-choice[2], -choice[1], -choice[0]]

    def __open_membrane(self, model_id, particle_height_offset):
        # path = "/data/kshin/T4SS_sim/mem_large.mrc"
        path = "/Users/kshin/Documents/data/T4SS/simulations/parallel_test/mem_large.mrc"
        self.commands.append('open #%d %s' % (model_id, path))
        self.commands.append('move 0,0,%d models #%d' % (particle_height_offset + 25, model_id))
        return model_id

    def __assemble_particle(self, output_filename):
        """
            Get one random orientation and angle and save one model file
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

        # Apply random position
        self.commands.append("move %.2f,%.2f,0 models #%d" % (random_position[0],
                                                              random_position[1], model))

        # Apply random angle with respect to the membrane
        random_angle = self.__get_random_angle()
        self.chosen_angles.append(random_angle)
        self.commands.append("turn y %.2f models #%d" % (random_angle, model))

        # Tack on membrane
        particle_height_offset = 75
        membrane_model = self.__open_membrane(100, particle_height_offset)

        # Commands to combine membrane and particle into one mrc
        final_model = 99
        self.commands.append("vop add #%d,#%d modelId #%d" % (membrane_model, model, final_model))

        # Save truth particle map
        self.commands.append("volume #%d save %s" % (final_model, output_filename))

        # Clear for the next particle
        self.commands.append("close session")

        return random_orientation, random_position, random_angle

    def __send_commands_to_chimera(self):
        # Now that we've built up the sequence of commands to generate the model, send to Chimera
        # Make sure to wait until the server is available by sending over the lock
        command_set = Chimera.ChimeraCommandSet(self.commands, self.pid, self.ack_event)
        command_set.send_and_wait(self.chimera_queue)

    def set_up_tiltseries(self, simulation):
        """
        For number of particles (i.e 4)
            Make a temp truth volume
            Assemble particle and save truth
            Set up sim configs and update TEM input files
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
        rmtree(self.temp_dir + "/truth_vols")

    def close(self):
        # Let the Chimera server know that this Assembler is done using the server
        self.commands = ["END"]
        self.__send_commands_to_chimera()
