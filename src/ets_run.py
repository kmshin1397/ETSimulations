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
from assemblers.t4ss_assembler import T4SSAssembler
from simulation.chimera_server import ChimeraServer
from simulation.logger import log_listener_process, metadata_log_listener_process


def configure_root_logger(queue):
    """ Helper function to initialize and configure the main logger instance to handle log messages.

    Args:
        queue: An instance of the  multiprocessing.queue class which provides thread-safe handling
            of log messages coming from many child processes.

    Returns: None

    """
    h = handlers.QueueHandler(queue)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.DEBUG)


def write_out_metadata_records(metadata_queue, filename):
    # Metadata objects for each stack
    metadata = []
    while not metadata_queue.empty():
        metadata.append(metadata_queue.get())

    # Log metadata
    metadata.sort(key=sort_on_id)
    metadata_file = filename
    with open(metadata_file, 'w') as f:
        f.write(json.dumps(metadata, indent=4))


def parse_inputs():
    """ Instantiate and set up the command line arguments parser for the ets_run module

    Returns: None

    """
    parser = argparse.ArgumentParser(
        description='Generate simulated tilt stacks and process them.')
    parser.add_argument('-i', '--input', required=True,
                        help='the input configurations YAML file')
    arguments = parser.parse_args()
    input_file = arguments.input
    stream = open(input_file, 'r')
    return yaml.load(stream)


def sort_on_id(simulation):
    """ Helper function used to sort the queue of metadata logs from a series of simulations by
    their stack numbers.

    Args:
        simulation: The src.simulation.Simulation class instance which represents one run of the
            TEM-Simulator

    Returns: the stack number within the set of simulations

    """
    return simulation["global_stack_no"]


def scale_and_invert_mrc(filename, apix=1.0):
    """ Given an outputted raw tilt stack from the TEM-Simulator, invert the images so that greater
    densities are darker and add voxel sizing information to the header.

    Args:
        filename: The path to the raw tiltseries MRC that should be processed

    Returns: None

    """
    data = np.array([])
    val_range = 0
    min_val = 0

    # We expect some MRC format warnings from the TEM-Simulator output
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import mrcfile
        # mrcfile.validate(filename)

        with mrcfile.open(filename, mode='r', permissive=True) as mrc:
            val_range = mrc.header.dmax - mrc.header.dmin
            min_val = mrc.header.dmin
            data = np.copy(mrc.data)

        new_file = "%s/%s_inverted.mrc" % (os.path.dirname(filename),
                                           os.path.splitext(os.path.basename(filename))[0])

        with mrcfile.new(new_file, overwrite=True) as mrc:
            data *= -1
            data += val_range + min_val
            mrc.set_data(data)
            mrc.voxel_size = apix


def run_process(args, pid, metadata_queue, chimera_commands_queue, ack_event, complete_event):
    """ Drives a single child process of the simulation pipeline.

    A temporary data directory is first created for use only by the child process. An Assembler
    instance is created, and for each tiltseries simulation assigned to the child process, the
    appropriate number of particles are assembled and passed along to the TEM-Simulator to simulate
    tilt stacks with.

    Args:
        args: The command line arguments passed to the main ets_run process
        pid: The process ID of this child process
        chimera_commands_queue: The multiprocessing queue where commands for the Chimera REST Server
            can be sent by the particle Assembler
        ack_event: A child process-specific multiprocessing Event to subscribe to in order to know
            when the Chimera commands we send off to the server have been completed

    Returns: None

    """

    root = args["root"]
    raw_data_dir = root + "/raw_data"

    project_name = args["name"]
    if project_name is None:
        project_name = os.path.basename(root)

    process_temp_dir = root + "/temp_%d" % pid
    os.mkdir(process_temp_dir)

    logger.info("Making process temp dir: %s" % process_temp_dir)

    # Copy over TEM-Simulator input files so it doesn't interfere with
    # any other potentially running simulations
    new_coord_file = process_temp_dir + "/T4SS_coord.txt"
    new_input_file = process_temp_dir + "/sim.txt"
    copyfile(args["coord"], new_coord_file)
    copyfile(args["config"], new_input_file)

    sim_input_file = new_input_file
    coord_file = new_coord_file

    num_stacks_per_cores = args["num_stacks"] // args["num_cores"]

    # If last core, tack on the remainder stacks as well
    if pid == args["num_cores"] - 1:
        num_stacks_per_cores += args["num_stacks"] % args["num_cores"]

    assembler = T4SSAssembler(args["model"], process_temp_dir, chimera_commands_queue,
                              ack_event, pid, args["custom_configs"])

    apix = None
    if "apix" in args:
        apix = args["apix"]

    for i in range(num_stacks_per_cores):
        progress_msg = "Simulating %d of %d tilt stacks assigned to CPU #%d" % (
            i + 1, num_stacks_per_cores, pid)
        logger.info(progress_msg)
        print(progress_msg)

        if i > 0:
            assembler.reset_temp_dir()

        global_id = pid * (args["num_stacks"] // args["num_cores"]) + i
        stack_dir = raw_data_dir + "/%s_%d" % (project_name, global_id)
        os.mkdir(stack_dir)

        tiltseries_file = stack_dir + "/%s_%d.mrc" % (project_name, global_id)
        nonoise_tilts_file = stack_dir + "/%s_%d_nonoise.mrc" % (project_name, global_id)

        sim = Simulation(sim_input_file, coord_file, tiltseries_file, nonoise_tilts_file,
                         global_id, process_temp_dir, apix=apix)

        # Pass along the simulation object to the assembler to set up a simulation run
        sim = assembler.set_up_tiltseries(sim)
        sim.edit_output_files()

        # Set up beads
        sim.create_fiducials(args["bead_map"])

        TEM_exec_path = args["tem_simulator_executable"]
        sim.run_tem_simulator(TEM_exec_path)
        scale_and_invert_mrc(tiltseries_file, args["apix"] * 10)

        logger.info("Enqueing metadata for tilt stack %d of %d" % (i + 1, num_stacks_per_cores))
        metadata_message = json.dumps(sim.get_metadata(), indent=2)
        metadata_queue.put(metadata_message)

        # Reset temporary copies of template files
        copyfile(args["coord"], coord_file)
        copyfile(args["config"], sim_input_file)

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
    """ Run the Chimera REST Server in a child process.

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
        base_request = "http://localhost:%d/run" % chimera.port

        if new_commands[0] == "END":
            logger.info("Received notice that process %d is finished with the server" %
                        requester_pid)
            finished_processes.append(requester_pid)
            process_events[requester_pid].set()
            # If that was the last process, quit the server
            if len(finished_processes) == len(process_events.keys()):
                break
            else:
                continue

        for c in new_commands:
            # If this is a close session command, it is coming after a save command so give a little
            # more time to let the save complete
            if c.startswith("close"):
                time.sleep(0.5)

            logger.debug("Making request: " + c)
            requests.get(base_request, params={'command': c})

        # Clean up
        # requests.get(base_request, params={'command': 'close session'})

        # Pass along an ack
        process_events[requester_pid].set()

    chimera.quit()


def main():
    """ The main driver process, which sets up top-level run directories and spawns necessary
    child processes.

    Returns: None

    """
    print("For detailed messages, logs can be found at:\n"
          + logfile)

    # Set up simulation file directories
    # Trailing slash not expected by rest of program
    args["root"] = args["root"].rstrip("/")
    raw_data_dir = args["root"] + "/raw_data"
    os.mkdir(raw_data_dir)

    # Set up parallel processes
    if "num_cores" not in args:
        num_cores = min(multiprocessing.cpu_count(), args["num_stacks"])
        args["num_cores"] = num_cores
    else:
        num_cores = min(args["num_cores"], args["num_stacks"])
        args["num_cores"] = num_cores
    num_cores = args["num_cores"]

    logger.info("Using %d cores" % num_cores)

    # Set up metadata log listener process #
    metadata_queue = multiprocessing.Queue()
    metadata_log = args["root"] + "/sim_metadata.json"
    metadata_process = multiprocessing.Process(target=metadata_log_listener_process,
                                               args=(metadata_queue, metadata_log))
    metadata_process.start()

    # Set up Chimera server processes #
    num_chimeras = args["num_chimera_windows"]
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

        process = multiprocessing.Process(target=run_process, args=(args, pid, metadata_queue,
                                                                    chimera_commands,
                                                                    ack_event, complete_event))
        processes.append(process)
        complete_processes.append(complete_event)

    for i in range(num_chimeras):
        chimera_commands, chimera_process_events = chimera_objects[i]

        # Start the Chimera server first, so it can be ready for the model assemblers
        chimera_process = multiprocessing.Process(target=run_chimera_server,
                                                  args=(args["chimera_exec_path"],
                                                        chimera_commands,
                                                        chimera_process_events))
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

        # metadata_file = args["root"] + "/sim_metadata.json"
        # write_out_metadata_records(metadata_queue, metadata_file)

        logger.info('An interrupt signal was received: ' + str(sig_num))
        if send_notification:
            send_email("kshin@umbriel.jensen.caltech.edu", args["email"],
                       "ETSimulations Status", 'Interrupt signal received')

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
        processes[i].join()

    for i, chimera_process in enumerate(chimera_processes):
        chimera_process.join()
        logger.info("Joined in Chimera process %d" % i)

    logger.info("Joined Chimera server processes")

    time_taken = (time.time() - start_time) / 60.

    metadata_queue.put("END")
    metadata_process.join()

    logger.info('Total time taken: %0.3f minutes' % time_taken)
    if send_notification:
        send_email("kshin@umbriel.jensen.caltech.edu", args["email"],
                   "Simulation complete", 'Total time taken: %0.3f minutes' % time_taken)


if __name__ == '__main__':
    start_time = time.time()
    logger = logging.getLogger(__name__)

    args = parse_inputs()
    if "name" not in args:
        args["name"] = os.path.basename(args["root"])

    if args["model"].endswith(".pdb") and "apix" not in args:
        print("An apix value must be provided with a PDB model!")
        exit(1)

    send_notification = False
    if "email" in args:
        send_notification = True

    # Start the logger process
    logs_queue = multiprocessing.Queue()
    logfile = "%s/%s.log" % (args["root"], args["name"])
    log_listener = multiprocessing.Process(target=log_listener_process, args=(logs_queue, logfile,
                                                                              start_time))
    log_listener.start()

    configure_root_logger(logs_queue)

    main()
    logs_queue.put("END")
    log_listener.join()
