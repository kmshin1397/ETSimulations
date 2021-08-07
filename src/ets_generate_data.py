""" This module is the main entry point for generating a set of simulated tilt stacks.

The tilt stacks are generated using the TEM-Simulator software package, taking as input a PDB or
MRC map file of a particular particle of interest and generating a cryo-EM image stack containing
the given particle. More complicated particle sources (i.e. randomizing the orientations of the
particles and adding membrane segments around them) can be used by providing a custom Assembler
class which interfaces with a Chimera REST Server to assemble these particle sources to feed in to
each run of the TEM-Simulator.

Kyung Min Shin, 2020

"""

# Built-in modules
import time
import os
import multiprocessing
from shutil import rmtree, copyfile
import argparse
import json
import requests
import logging
from logging import handlers
import signal
import warnings

# External modules
import numpy as np
import yaml

# Custom modules
from simulation.notify import send_email
from simulation.tem_simulation import Simulation
from assemblers.basic_assembler import BasicAssembler
from assemblers.t4ss_assembler import T4SSAssembler
from simulation.chimera_server import ChimeraServer
from simulation.logger import log_listener_process, metadata_log_listener_process


assembler_registry = {"basic": BasicAssembler, "t4ss": T4SSAssembler}


def configure_root_logger(queue):
    """Helper function to initialize and configure the main logger instance to handle log messages.

    Args:
        queue: An instance of the  multiprocessing.queue class which provides thread-safe handling
            of log messages coming from many child processes.

    Returns: None

    """
    h = handlers.QueueHandler(queue)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.DEBUG)


def parse_inputs():
    """Instantiate and set up the command line arguments parser for the ets_generate_data module

    Returns: None

    """
    parser = argparse.ArgumentParser(description="Generate simulated tilt stacks")
    parser.add_argument(
        "-i", "--input", required=True, help="the input configurations YAML file"
    )
    arguments = parser.parse_args()
    input_file = arguments.input
    stream = open(input_file, "r")
    return yaml.load(stream, Loader=yaml.FullLoader)


def scale_mrc(filename, apix=1.0):
    """Given an outputted raw tilt stack from the TEM-Simulator, add voxel sizing information to
    the header.

    Args:
        filename: The path to the raw tiltseries MRC that should be processed
        apix: The voxel size

    Returns: None

    """

    # We expect some MRC format warnings from the TEM-Simulator output
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import mrcfile

        data = np.array([])
        with mrcfile.open(filename, mode="r", permissive=True) as mrc:
            data = np.copy(mrc.data)

        new_file = "%s/%s.mrc" % (
            os.path.dirname(filename),
            os.path.splitext(os.path.basename(filename))[0],
        )

        with mrcfile.new(new_file, overwrite=True) as mrc:
            mrc.set_data(data)
            mrc.voxel_size = apix


def get_defocus_value(defocuses, global_stack_no):
    num_defocuses = len(defocuses)
    return defocuses[global_stack_no % num_defocuses]


def run_process(
    configs, pid, metadata_queue, chimera_commands_queue, ack_event, complete_event
):
    """Drives a single child process of the simulation pipeline.

    A temporary data directory is first created for use only by the child process. An Assembler
    instance is created, and for each tiltseries simulation assigned to the child process, the
    appropriate number of particles are assembled and passed along to the TEM-Simulator to simulate
    tilt stacks with.

    Args:
        configs: The command line arguments passed to the main ets_generate_data process
        pid: The process ID of this child process
        metadata_queue: The multiprocessing queue used for sending metadata log messages to the
            central log listener
        chimera_commands_queue: The multiprocessing queue where commands for the Chimera REST Server
            can be sent by the particle Assembler
        ack_event: A child process-specific multiprocessing Event to subscribe to in order to know
            when the Chimera commands we send off to the server have been completed
        logger: Python logging module logger to send logs to
        complete_event: A child process-specific multiprocessing Event used to indicate to the main
            process that this child has finished processing its jobs

    Returns: None

    """
    root = configs["root"]
    raw_data_dir = root + "/raw_data"

    project_name = configs["name"]
    if project_name is None:
        project_name = os.path.basename(root)

    process_temp_dir = root + "/temp_%d" % pid
    os.mkdir(process_temp_dir)

    logger.info("Making process temp dir: %s" % process_temp_dir)

    # Copy over TEM-Simulator input files so it doesn't interfere with
    # any other potentially running simulations
    new_coord_file = process_temp_dir + "/coord.txt"
    new_input_file = process_temp_dir + "/sim.txt"
    copyfile(configs["coord"], new_coord_file)
    copyfile(configs["config"], new_input_file)

    sim_input_file = new_input_file
    coord_file = new_coord_file

    num_stacks_per_cores = configs["num_stacks"] // configs["num_cores"]

    # If there are extra stacks (not evenly divisible) spread out the remainder
    remainder = configs["num_stacks"] % configs["num_cores"]
    if remainder != 0 and pid < remainder:
        num_stacks_per_cores += 1

    assembler_type = configs["assembler"]
    assembler = assembler_registry[assembler_type](
        configs["model"],
        process_temp_dir,
        chimera_commands_queue,
        ack_event,
        pid,
        configs["custom_configs"],
    )

    apix = None
    if "apix" in configs:
        apix = configs["apix"]

    for i in range(num_stacks_per_cores):
        progress_msg = "Simulating %d of %d tilt stacks assigned to CPU #%d" % (
            i + 1,
            num_stacks_per_cores,
            pid,
        )
        logger.info(progress_msg)
        print(progress_msg)

        if i > 0:
            assembler.reset_temp_dir()

        remainders_assigned_before = min(pid, remainder)
        global_id = (
            pid * (configs["num_stacks"] // configs["num_cores"])
            + i
            + remainders_assigned_before
        )

        stack_dir = raw_data_dir + "/%s_%d" % (project_name, global_id)
        os.mkdir(stack_dir)

        tiltseries_file = stack_dir + "/%s_%d.mrc" % (project_name, global_id)
        nonoise_tilts_file = stack_dir + "/%s_%d_nonoise.mrc" % (
            project_name,
            global_id,
        )

        # Grab a defocus value for this simulation
        defocus = get_defocus_value(configs["defocus_values"], global_id)

        sim = Simulation(
            sim_input_file,
            coord_file,
            tiltseries_file,
            nonoise_tilts_file,
            global_id,
            process_temp_dir,
            apix=apix,
            defocus=defocus,
            template_configs=configs["config"],
            template_coords=configs["coord"],
        )

        # Pass along the simulation object to the assembler to set up a simulation run
        assembler.set_up_tiltseries(sim)
        sim.edit_output_files()

        # Set up beads
        sim.create_fiducials(configs["bead_map"], configs["bead_occupancy"])

        TEM_exec_path = configs["tem_simulator_executable"]
        sim.run_tem_simulator(TEM_exec_path)
        scale_mrc(tiltseries_file, configs["apix"] * 10)

        logger.info(
            "Enqueing metadata for tilt stack %d of %d" % (i + 1, num_stacks_per_cores)
        )
        metadata_message = json.dumps(sim.get_metadata(), indent=2)
        metadata_queue.put(metadata_message)

        # Reset temporary copies of template files
        copyfile(configs["coord"], coord_file)
        copyfile(configs["config"], sim_input_file)

        sim.close()

        # If this is the last stack for this process, clean up the Assembler
        if i == num_stacks_per_cores - 1:
            logger.debug("Closing Assembler")
            assembler.close()

    # Clean up temp files
    logger.debug("Removing temp dir")
    rmtree(process_temp_dir)

    logger.debug("Closing sub-process %d" % pid)

    print("Returning from subprocess %d" % pid)
    complete_event.set()
    return


def run_chimera_server(chimera_path, commands_queue, process_events):
    """Run the Chimera REST Server in a child process.

    ETSimulations uses a REST Server instance of Chimera to allow Assembler modules to build up
    particle models, shared by all multiprocessing child processes. Each child process whose
    Assembler wishes to use the Chimera server will send the entire set of commands to generate
    a model so that Chimera sessions remain separate.

    Args:
        chimera_path:
        commands_queue: The multiprocessing queue which maintains thread-safe piping of Chimera
            commands to make HTTP GET requests with, filled by particle Assemblers in other
            processes
        process_events: A dictionary linking each child process ID to its process-specific
            multiprocessing acknowledgement event which signals to Assemblers when the commands
            sent by that Assembler have been completed

    Returns: None

    """
    chimera = ChimeraServer(chimera_path)
    chimera.start_chimera_server()

    finished_processes = []

    while True:
        requester_pid, new_commands = commands_queue.get()
        base_request = "http://localhost:%d/run" % chimera.get_port()

        if new_commands[0] == "END":
            logger.info(
                "Received notice that process %d is finished with the server"
                % requester_pid
            )
            finished_processes.append(requester_pid)
            process_events[requester_pid].set()
            # If that was the last process, quit the server
            if len(finished_processes) == len(process_events.keys()):
                break
            else:
                continue

        i = 0
        while i < len(new_commands):
            c = new_commands[i]
            # If this is a close session command, it is coming after a save command so give a little
            # more time to let the save complete
            if c.startswith("close"):
                time.sleep(0.5)

            try:
                logger.debug("Making request: " + c)
                logger.debug(
                    "This is command #%d for this batch from process %d"
                    % (i, requester_pid)
                )
                requests.get(base_request, params={"command": c}, timeout=600)
                # time.sleep(2)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                # If the Chimera server hasn't responded in 10 minutes, restart it
                logger.info(
                    "Chimera server at port %d is unresponsive. Restarting..."
                    % chimera.get_port()
                )
                chimera.restart_chimera_server()
                base_request = "http://localhost:%d/run" % chimera.get_port()
                # Restart this particle's assembly
                i = 0
                continue

            i += 1

        # Clean up in case the Assembler did not
        requests.get(base_request, params={"command": "close session"})

        # Pass along an ack
        process_events[requester_pid].set()

    chimera.quit()


def start_logger(logs_queue, logfile):
    """Start the multiprocessing logging process

    Args:
        logs_queue: A multiprocessing queue to take in and digest log messages
        logfile: The output text file to log to

    Returns: The child process of the log listener

    """
    log_listener = multiprocessing.Process(
        target=log_listener_process, args=(logs_queue, logfile, start_time)
    )
    log_listener.start()
    configure_root_logger(logs_queue)
    return log_listener


def main(configs):
    """The main driver process, which sets up top-level run directories and spawns necessary
    child processes.

    Returns: None

    """
    logs_queue = multiprocessing.Queue()
    logfile = "%s/%s.log" % (configs["root"], configs["name"])
    log_listener = start_logger(logs_queue, logfile)

    print("For detailed messages, logs can be found at:\n" + logfile)

    # Set up simulation file directories
    # Trailing slash not expected by rest of program
    configs["root"] = configs["root"].rstrip("/")
    raw_data_dir = configs["root"] + "/raw_data"
    if not os.path.exists(raw_data_dir):
        os.mkdir(raw_data_dir)
    else:
        print(
            "A raw_data directory already exists in this root folder!\n"
            "Please remove/rename the existing folder."
        )
        exit(1)

    # Set up parallel processes
    if "num_cores" not in configs:
        num_cores = min(multiprocessing.cpu_count(), configs["num_stacks"])
        configs["num_cores"] = num_cores
    else:
        num_cores = min(configs["num_cores"], configs["num_stacks"])
        configs["num_cores"] = num_cores
    num_cores = configs["num_cores"]

    logger.info("Using %d cores" % num_cores)

    # Set up metadata log listener process #
    metadata_queue = multiprocessing.Queue()
    metadata_log = configs["root"] + "/sim_metadata.json"
    metadata_process = multiprocessing.Process(
        target=metadata_log_listener_process, args=(metadata_queue, metadata_log)
    )
    metadata_process.start()

    # Set up Chimera server processes #
    num_chimeras = configs["num_chimera_windows"]
    chimera_objects = []
    chimera_processes = []
    for i in range(num_chimeras):
        # Shared Queue to pass along sets of Chimera commands to pass along to the server
        chimera_commands = multiprocessing.Queue()

        # Create a set of subprocess-specific events to signal command completions to them
        chimera_process_events = {}

        chimera_objects.append((chimera_commands, chimera_process_events))

    # Set up the child processes to run the model assembly/simulations #
    # We wait until all processes are set up before starting them, so that the Chimera sever process
    # can be made aware of all processes (and be passes all their acknowledge events).
    processes = []
    complete_processes = []
    for pid in range(num_cores):
        # Event unique to each child process used to subscribe to a Chimera server command set
        # and listen for completion of commands request.
        ack_event = multiprocessing.Event()
        complete_event = multiprocessing.Event()

        chimera_index = pid % num_chimeras
        chimera_commands, chimera_process_events = chimera_objects[chimera_index]

        chimera_process_events[pid] = ack_event
        process = multiprocessing.Process(
            target=run_process,
            args=(
                configs,
                pid,
                metadata_queue,
                chimera_commands,
                ack_event,
                complete_event,
            ),
        )
        processes.append(process)
        complete_processes.append(complete_event)

    # When using the Basic Assembler with use_common_model mode, we don't need Chimera servers
    if not (
        configs["assembler"] == "basic"
        and configs["custom_configs"]["use_common_model"]
    ):
        for i in range(num_chimeras):
            chimera_commands, chimera_process_events = chimera_objects[i]

            # Start the Chimera server first, so it can be ready for the model assemblers
            chimera_process = multiprocessing.Process(
                target=run_chimera_server,
                args=(
                    configs["chimera_exec_path"],
                    chimera_commands,
                    chimera_process_events,
                ),
            )
            logger.info("Starting Chimera server process")
            chimera_process.start()

            chimera_processes.append(chimera_process)

    # Now start all the processes
    for i, process in enumerate(processes):
        process.start()

    # register the signals to be caught
    def on_kill_signal(sig_num, frame):

        for i, p in enumerate(multiprocessing.active_children()):
            p.terminate()
            logger.info("Terminated process %d" % i)

        logger.info("An interrupt signal was received: " + str(sig_num))
        # if "email" in configs:
        #     send_email("kshin@umbriel.jensen.caltech.edu", configs["email"],
        #                "ETSimulations Status", 'Interrupt signal received')

        exit(1)

    signal.signal(signal.SIGHUP, on_kill_signal)
    signal.signal(signal.SIGINT, on_kill_signal)
    signal.signal(signal.SIGQUIT, on_kill_signal)
    signal.signal(signal.SIGILL, on_kill_signal)
    signal.signal(signal.SIGABRT, on_kill_signal)
    signal.signal(signal.SIGBUS, on_kill_signal)
    signal.signal(signal.SIGFPE, on_kill_signal)
    signal.signal(signal.SIGSEGV, on_kill_signal)
    signal.signal(signal.SIGPIPE, on_kill_signal)
    signal.signal(signal.SIGALRM, on_kill_signal)
    signal.signal(signal.SIGTERM, on_kill_signal)

    for i, event in enumerate(complete_processes):
        logger.info("Waiting for process %d" % i)
        event.wait()

        logger.info("Got completion signal from process %d" % i)
        # processes[i].join()
        """ NOTE: We use terminate to force kill the child processes instead of joining them in 
        because for reasons I have yet to figure out the children hang upon finishing their 
        processing. We know everything should be done since we wait for a signal at the very end of 
        the processing function, so I think it's okay to just terminate the children for now - to be
        investigated more in the future"""
        processes[i].terminate()

    if not (
        configs["assembler"] == "basic"
        and configs["custom_configs"]["use_common_model"]
    ):
        for i, chimera_process in enumerate(chimera_processes):
            chimera_process.join()
            logger.info("Joined in Chimera process %d" % i)

        logger.info("Joined Chimera server processes")

    time_taken = (time.time() - start_time) / 60.0

    metadata_queue.put("END")
    metadata_process.join()

    logger.info("Total time taken: %0.3f minutes" % time_taken)

    # if "email" in configs:
    #     send_email("kshin@umbriel.jensen.caltech.edu", configs["email"],
    #                "Simulation complete", 'Total time taken: %0.3f minutes' % time_taken)

    logs_queue.put("END")
    log_listener.join()


logger = None
start_time = time.time()

if __name__ == "__main__":

    logger = logging.getLogger(__name__)

    args = parse_inputs()
    if "name" not in args:
        args["name"] = os.path.basename(args["root"])

    if args["model"].endswith(".pdb") and "apix" not in args:
        print("An apix value must be provided with a PDB model!")
        exit(1)

    main(args)
