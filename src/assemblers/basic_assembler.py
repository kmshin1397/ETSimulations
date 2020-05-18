# Built-in modules
import os
from shutil import rmtree
import logging

# External packages

# Custom modules
from simulation.particle_set import ParticleSet
from simulation import chimera_server as chimera

logger = logging.getLogger(__name__)


class BasicAssembler:
    def __init__(self, model, temp_dir, chimera_queue, ack_event, pid):
        self.model = model
        self.temp_dir = temp_dir
        self.commands = []
        self.chimera_queue = chimera_queue

        # Event unique to each child process used to subscribe to a Chimera server command set
        # and listen for completion of commands request.
        self.ack_event = ack_event

        # An instance of the Simulation class that holds current iteration TEM-Simulator parameters
        self.simulation = None

        # The subprocess ID of the worker using this Assembler
        self.pid = pid

    def __assemble_particle(self, output_filename):
        """
            This is a simple assembly module which just saves the passed in model to a new location
            where the TEM-Simulator can find it
        """

        # Clear state variables
        model_id = 0

        # The first Chimera command is to open the template model file
        self.commands.append('open #%d %s' % (model_id, self.model))

        # Now we just save it to the desired location passed in
        self.commands.append("volume #%d save %s" % (model_id, output_filename))

        # Clear for the next particle
        self.commands.append("close session")

    def __send_commands_to_chimera(self):
        # Now that we've built up the sequence of commands to generate the model, send to Chimera
        # Make sure to wait until the server is available by sending over the lock
        command_set = chimera.ChimeraCommandSet(self.commands, self.pid, self.ack_event)
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

        custom_metadata = {"your_custom_information_to_log": []}

        # Initialize a Particle Set instance to add individual particles to a stack
        particle_set = ParticleSet("BasicParticle", key=True)

        for i in range(num_particles):
            new_particle = truth_vols_dir + "/%d.mrc" % i

            # Assemble a new particle
            self.__assemble_particle(new_particle)

            # Update the simulation parameters with the new particle

            # These basic particles will all just get an orientation of zero rotations
            particle_set.add_orientation([0, 0, 0])

            particle_set.add_coordinate(coordinates[i])
            particle_set.add_source(new_particle)
            particle_set.num_particles += 1

            custom_metadata["your_custom_information_to_log"].append("some_custom_log_info")

        # Now send off the Chimera commands you have compiled for this stack off to the Chimera
        # server to be processed
        self.__send_commands_to_chimera()

        # Apply completed particle set to TEM-Simulator configs
        self.simulation.create_particle_lists([particle_set])

        self.simulation.custom_data = custom_metadata

        return self.simulation

    def reset_temp_dir(self):
        rmtree(self.temp_dir + "/truth_vols")

    def close(self):
        # Let the Chimera server know that this Assembler is done using the server
        self.commands = ["END"]
        self.__send_commands_to_chimera()
