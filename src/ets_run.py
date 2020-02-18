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

# External modules
import mrcfile
import numpy as np

# Custom modules
from src.notify import send_email
from src.simulation import Simulation
from src.t4ss_assembler import T4SSAssembler
from src.chimera_server import ChimeraServer
from src.logger import log_listener_process


TEM_exec_path = "/Users/kshin/Documents/software/TEM-simulator_1.3/src/TEM-simulator"

# Root logger configuration
def configure_root_logger(queue):
    h = handlers.QueueHandler(queue)
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.INFO)


def parse_inputs():
    parser = argparse.ArgumentParser(
        description='Generate simulated tilt stacks and process them.')
    parser.add_argument('-m', '--model', required=True,
                        help='the particle model (pdb or mrc) to insert into tilt stacks')
    parser.add_argument('-r', '--root', required=True,
                        help='the project root directory in which to store generated files')
    parser.add_argument('-cfg', '--config', required=True,
                        help='the TEM-Simulator configuration file to use for each tilt stack')
    parser.add_argument('-c', '--coord', required=True,
                        help='the particle coordinates file for the TEM-Simulator')
    parser.add_argument('-n', '--num_stacks', required=True, type=int,
                        help='the number of tilt stacks to generate')
    parser.add_argument('--num_cores', type=int,
                        help='the number of CPU cores to use (default: all)')
    parser.add_argument('--name',
                        help='project base name to use when naming files (default taken from root '
                             'directory name)')
    parser.add_argument('--email', default='',
                        help='email address to send completion notification to')
    parser.add_argument('--keep_tmp', action='store_true', default=False,
                        help='enable to store all temporary files generated (currently just the '
                             'truth volume of the simulated tilt stacks. (NOT IMPLEMENTED)')
    parser.add_argument('--apix', type=float,
                        help="required if providing a pdb file as the model source")
    return parser.parse_args()


def sort_on_id(simulation):
    return simulation["global_stack_no"]


def scale_and_invert_mrc(filename):
    mrcfile.validate(filename)
    data = np.array([])
    val_range = 0
    min_val = 0
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
        mrc.voxel_size = 2.83


def run_process(args, pid, chimera_commands_queue, ack_event):
    keep_temps = args.keep_tmp

    root = args.root
    raw_data_dir = root + "/raw_data"

    project_name = args.name
    if project_name is None:
        project_name = os.path.basename(root)

    process_temp_dir = root + "/temp_%d" % pid
    os.mkdir(process_temp_dir)

    logger.info("Making process temp dir: %s" % process_temp_dir)

    # Copy over TEM-Simulator input files so it doesn't interfere with
    # any other potentially running simulations
    new_coord_file = process_temp_dir + "/T4SS_coord.txt"
    new_input_file = process_temp_dir + "/sim.txt"
    copyfile(args.coord, new_coord_file)
    copyfile(args.config, new_input_file)

    sim_input_file = new_input_file
    coord_file = new_coord_file

    num_stacks_per_cores = args.num_stacks // args.num_cores

    # If last core, tack on the remainder stacks as well
    if pid == args.num_cores - 1:
        num_stacks_per_cores += args.num_stacks % args.num_cores

    assembler = T4SSAssembler(args.model, process_temp_dir, chimera_commands_queue,
                              ack_event, pid)

    for i in range(num_stacks_per_cores):
        progress_msg = "Simulating %d of %d tilt stacks assigned to CPU #%d" % (
            i + 1, num_stacks_per_cores, pid)
        logger.info(progress_msg)
        print(progress_msg)

        if i > 0:
            assembler.reset_temp_dir()

        global_id = pid * num_stacks_per_cores + i
        stack_dir = raw_data_dir + "/%s_%d" % (project_name, global_id)
        os.mkdir(stack_dir)

        tiltseries_file = stack_dir + "/%s_%d.mrc" % (project_name, global_id)
        nonoise_tilts_file = stack_dir + "/%s_%d_nonoise.mrc" % (project_name, global_id)

        sim = Simulation(sim_input_file, coord_file, tiltseries_file, nonoise_tilts_file,
                         global_id, process_temp_dir, apix=args.apix)

        # Pass along the simulation object to the assembler to set up a simulation run
        sim = assembler.set_up_tiltseries(sim)
        sim.edit_output_files()

        # If this is the last stack for this process, clean up the Assembler
        assembler.close()

        sim.run_tem_simulator(TEM_exec_path)
        scale_and_invert_mrc(tiltseries_file)

        metadata_queue.put(sim.get_metadata())

    # Clean up temp files if desired
    if not keep_temps:
        rmtree(process_temp_dir)


def run_chimera_server(commands_queue, process_events):
    # ETSimulations uses a REST Server instance of Chimera to allow Assembler modules to build up
    # particle models, shared by all multiprocessing child processes. Each child process whose
    # Assembler wishes to use the Chimera server will send the entire set of commands to generate
    # a model so that Chimera sessions remain separate.
    chimera = ChimeraServer()
    chimera.start_chimera_server()

    finished_processes = []

    while True:
        requester_pid, new_commands = commands_queue.get()
        base_request = "http://localhost:%d/run" % chimera.port

        if new_commands[0] == "END":
            logger.info("Received notice that process %d is finished with the server" %
                        requester_pid)
            finished_processes.append(requester_pid)
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

            logger.info("Making request: " + c)
            requests.get(base_request, params={'command': c})

        # Clean up
        requests.get(base_request, params={'command': 'close session'})

        # Pass along an ack
        process_events[requester_pid].set()

    chimera.quit()


def main():
    print("For detailed messages, logs can be found at:\n"
          + logfile)
    send_notification = False
    if args.email != '':
        send_notification = True

    # Set up simulation file directories
    # Trailing slash not expected by rest of program
    args.root = args.root.rstrip("/")
    raw_data_dir = args.root + "/raw_data"
    os.mkdir(raw_data_dir)

    # Set up parallel processes
    num_cores = args.num_cores
    if num_cores is None:
        num_cores = min(multiprocessing.cpu_count(), args.num_stacks)
        args.num_cores = num_cores

    logger.info("Using %d cores" % num_cores)

    # Shared Queue to pass along sets of Chimera commands to pass along to the server
    chimera_commands = multiprocessing.Queue()

    # Create a set of subprocess-specific events to signal command completions to them
    chimera_process_events = {}

    # Set up the child processes to run the model assembly/simulations.
    # We wait until all processes are set up before starting them, so that the Chimera sever process
    # can be made aware of all processes (and be passes all their acknowledge events).
    processes = []
    for pid in range(num_cores):

        # Event unique to each child process used to subscribe to a Chimera server command set
        # and listen for completion of commands request.
        ack_event = multiprocessing.Event()
        chimera_process_events[pid] = ack_event

        process = multiprocessing.Process(target=run_process, args=(args, pid, chimera_commands,
                                                                    ack_event))
        processes.append(process)

    # Start the Chimera server first, so it can be ready for the model assemblers
    chimera_process = multiprocessing.Process(target=run_chimera_server,
                                              args=(chimera_commands, chimera_process_events))
    logger.info("Starting Chimera server process")
    chimera_process.start()

    # Now start all the processes
    for i, process in enumerate(processes):
        process.start()

    for process in processes:
        process.join()

    time_taken = (time.time() - start_time) / 60.

    # Metadata objects for each stack
    metadata = []
    while not metadata_queue.empty():
        metadata.append(metadata_queue.get())

    # Log metadata
    metadata.sort(key=sort_on_id)
    metadata_file = args.root + "/sim_metadata.json"
    with open(metadata_file, 'w') as f:
        f.write(json.dumps(metadata, indent=4))

    logger.info('Total time taken: %0.3f minutes' % time_taken)
    if send_notification:
        send_email("kshin@umbriel.jensen.caltech.edu", args.email,
                   "Simulation complete", 'Total time taken: %0.3f minutes' % time_taken)


if __name__ == '__main__':
    start_time = time.time()
    logger = logging.getLogger(__name__)

    args = parse_inputs()
    if args.name is None:
        args.name = os.path.basename(args.root)

    if args.model.endswith(".pdb") and args.apix is None:
        print("An apix value must be provided with a PDB model!")
        exit(1)

    metadata_queue = multiprocessing.Queue()

    # Start the logger process
    logs_queue = multiprocessing.Queue()
    logfile = "%s/%s.log" % (args.root, args.name)
    log_listener = multiprocessing.Process(target=log_listener_process, args=(logs_queue, logfile,
                                                                              start_time))
    log_listener.start()

    configure_root_logger(logs_queue)

    main()
    logs_queue.put("END")
    log_listener.join()
