# Built-in modules
import time
import os
import multiprocessing
from shutil import rmtree, copyfile
import argparse
import json
import requests

# External modules
import mrcfile
import numpy as np

# Custom modules
from notify import send_email
from Simulation import Simulation
from T4SSAssembler import T4SSAssembler
from ChimeraServer import ChimeraServer


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
                             'truth volume of the simulated tilt stacks')
    parser.add_argument('--add_membrane', action='store_true', default=False,
                        help='enable to insert a membrane segment above each particle model within'
                             'the simulation - can be used with simulation of membrane-bound '
                             'complexes, for example')
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


def run_process(args, pid, chimera_commands_queue, chimera_acks):
    keep_temps = args.keep_tmp

    root = args.root
    raw_data_dir = root + "/raw_data"

    project_name = args.name
    if project_name is None:
        project_name = os.path.basename(root)

    process_temp_dir = root + "/temp_%d" % pid
    os.mkdir(process_temp_dir)

    print("Making process temp dir: %s" % process_temp_dir)

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

    assembler = T4SSAssembler(args.model, process_temp_dir, chimera_commands_queue, chimera_acks)

    for i in range(num_stacks_per_cores):
        log_msg = "Simulating %d of %d tilt stacks assigned to CPU #%d" % (
            i + 1, num_stacks_per_cores, pid)
        print(log_msg)
        # log(log_file, log_msg)

        if i > 0:
            assembler.reset_temp_dir()

        global_id = pid * num_stacks_per_cores + i
        stack_dir = raw_data_dir + "/%s_%d" % (project_name, global_id)
        os.mkdir(stack_dir)

        tiltseries_file = stack_dir + "/%s_%d.mrc" % (project_name, global_id)
        nonoise_tilts_file = stack_dir + "/%s_%d_nonoise.mrc" % (project_name, global_id)

        sim = Simulation(sim_input_file, coord_file, tiltseries_file, nonoise_tilts_file,
                         global_id, process_temp_dir)

        # Pass along the simulation object to the assembler to set up a simulation run
        sim = assembler.set_up_tiltseries(sim)
        sim.edit_output_files()

        sim.run_tem_simulator()
        scale_and_invert_mrc(tiltseries_file)

        metadata_queue.put(sim.get_metadata())

    # Clean up temp files if desired
    if not keep_temps:
        rmtree(process_temp_dir)


def main():
    send_notification = False
    if args.email != '':
        send_notification = True

    start_time = time.time()

    # Set up simulation file directories
    # Trailing slash not expected by rest of program
    args.root = args.root.rstrip("/")
    raw_data_dir = args.root + "/raw_data"
    os.mkdir(raw_data_dir)

    # Wait until Chimera listener is ready
    chimera_acknowledge.get()

    # Set up parallel processes
    num_cores = args.num_cores
    if num_cores is None:
        num_cores = multiprocessing.cpu_count()
        args.num_cores = num_cores

    print("Using %d cores" % num_cores)

    processes = []

    for i in range(num_cores):
        process = multiprocessing.Process(target=run_process, args=(args, i, chimera_commands,
                                                                    chimera_acknowledge))
        processes.append(process)
        print("Starting process %d" % i)
        process.start()

    for process in processes:
        process.join()

    chimera_commands.put(["done"])

    time_taken = (time.time() - start_time) / 60.
    # log(sim.log_file, 'Total time taken: %0.3f minutes' % time_taken)
    # log(metadata_file, "]")

    # Metadata objects for each stack
    metadata = []
    while not metadata_queue.empty():
        metadata.append(metadata_queue.get())

    metadata.sort(key=sort_on_id)
    metadata_file = args.root + "/sim_metadata.log"
    with open(metadata_file, 'w') as f:
        f.write(json.dumps(metadata, indent=4))

    print('Total time taken: %0.3f minutes' % time_taken)
    if send_notification:
        send_email("kshin@umbriel.jensen.caltech.edu", args.email,
                   "Simulation complete", 'Total time taken: %0.3f minutes' % time_taken)


def run_chimera_server(commands_queue, ack_queue):
    # ETSimulations uses a REST Server instance of Chimera to allow Assembler modules to build up
    # particle models, shared by all multiprocessing child processes. Each child process whose
    # Assembler wishes to use the Chimera server must first acquire the server's lock, and upon
    # model assembly completion relinquish the lock as well as clearing the Chimera session.
    chimera = ChimeraServer()
    chimera.start_chimera_server()

    # Let main process know that the Chimera server worker is up and ready
    ack_queue.put(200)
    while True:
        print("Starting server reader")
        new_commands = commands_queue.get()
        base_request = "http://localhost:%d/run" % chimera.port

        for c in new_commands:
            # If this is a close session command, it is coming after a save command so give a little
            # more time to let the save complete
            if c.startswith("close"):
                time.sleep(0.5)

            print("Making request: " + c)
            requests.get(base_request, params={'command': c})

        # Clean up
        r = requests.get(base_request, params={'command': 'close session'})

        # Pass along an ack
        ack_queue.put(r.status_code)

        if new_commands[0] == "done":
            break

    chimera.quit()

if __name__ == '__main__':
    args = parse_inputs()

    metadata_queue = multiprocessing.Queue()

    # Shared Queue to pass along sets of Chimera commands to pass along to the server
    chimera_commands = multiprocessing.Queue()

    # Shared Queue to pass along acknowledgements of Chimera command request completion
    chimera_acknowledge = multiprocessing.Queue()

    # chimera_server_lock = multiprocessing.Lock()
    chimera_process = multiprocessing.Process(target=run_chimera_server, args=(chimera_commands,
                                                                               chimera_acknowledge))
    chimera_process.start()
    main()

    chimera_process.join()
