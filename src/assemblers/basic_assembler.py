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
    """
    An example bare minimum Assembler implementation which just opens an MRC to use as the "assembled" particle.

    Attributes:
        model: The path to the model MRC to use as the particle
        temp_dir: The directory into which temporary truth volumes should be placed
        chimera_queue: The multiprocessing queue that the server process is listening to
        ack_event: The child process-specific acknowledgement event to subscribe to for
            completion notifications from the Chimera server
        pid: The ID of the child process running this assembler
        commands: The list of Chimera commands accrued by the Assembler during processing, to be
            sent to the Chimera REST server once ready
        simulation: The src.simulation.tem_simulation.Simulation object responsible for feeding
            particles assembled here to a TEM-Simulator run

    """
    def __init__(self, model, temp_dir, chimera_queue, ack_event, pid, custom_args):
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

        self.custom_args = custom_args

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
        """
        Create a Chimera Command Set object with the current commands stored in the Assembler and
            send them off to the server

        Returns: None

        """
        # Now that we've built up the sequence of commands to generate the model, send to Chimera
        # Make sure to wait until the server is available by sending over the lock
        command_set = chimera.ChimeraCommandSet(self.commands, self.pid, self.ack_event)
        command_set.send_and_wait(self.chimera_queue)

    def set_up_tiltseries(self, simulation):
        """
        Implements the basic tiltseries set-up procedure, which consists of:

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

        # Get particle coordinates from base file provided
        num_particles = self.simulation.get_num_particles()
        coordinates = self.simulation.parse_coordinates()

        truth_vols_dir = self.temp_dir + "/truth_vols"
        os.mkdir(truth_vols_dir)

        custom_metadata = {"your_custom_information_to_log": []}

        # Initialize a Particle Set instance to add individual particles to a stack
        particle_set = ParticleSet("BasicParticle", key=True)

        for i in range(num_particles):

            if not self.custom_args["use_common_model"]:
                new_particle = truth_vols_dir + "/%d.mrc" % i

                # Assemble a new particle
                self.__assemble_particle(new_particle)
            else:
                new_particle = self.model

            # Update the simulation parameters with the new particle

            # These basic particles will all just get an orientation of zero rotations
            particle_set.add_orientation([0, 0, 0])

            particle_set.add_coordinate(coordinates[i])
            particle_set.add_source(new_particle)
            particle_set.num_particles += 1

            custom_metadata["your_custom_information_to_log"].append("some_custom_log_info")

        # Now send off the Chimera commands you have compiled for this stack off to the Chimera
        # server to be processed (if we used Chimera, as use_common_map mode will not
        if not self.custom_args["use_common_model"]:
            self.__send_commands_to_chimera()

        # Apply completed particle set to TEM-Simulator configs
        self.simulation.create_particle_lists([particle_set])

        self.simulation.custom_data = custom_metadata

        return self.simulation

    def reset_temp_dir(self):
        """
        Resets the temp directory resources for the Assembler, i.e removes current particles created

        Returns: None

        """
        rmtree(self.temp_dir + "/truth_vols")

    def close(self):
        """
        Lets the Chimera server know that this Assembler is done for good

        Returns: None

        """
        # Let the Chimera server know that this Assembler is done using the server
        if not self.custom_args["use_common_model"]:
            self.commands = ["END"]
            self.__send_commands_to_chimera()
