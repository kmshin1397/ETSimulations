# Built-in modules
import time
import os
import multiprocessing
from shutil import move, rmtree, copyfile
import random
import argparse
import json

# External modules
import requests
import mrcfile
import numpy as np

# Custom modules
from notify import send_email
import chimera_server as chimera
from Simulation import Simulation
import tem_simulator_utils as tem_utils

metadata_queue = multiprocessing.Queue()


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
    parser.add_argument('-n', '--num_stacks', required=True,
                        help='the number of tilt stacks to generate')
    parser.add_argument('--num_cores', help='the number of CPU cores to use (default: all)')
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
    args = parser.parse_args()

    return args


# TODO Move into custom Assembler
def get_random_position():
    x = random.randrange(-125, 125, 1)
    y = random.randrange(-125, 125, 1)

    return (x, y)


# TODO Move into custom Assembler
def open_membrane(commands, model_id, particle_height_offset):
    path = "/data/kshin/T4SS_sim/mem_large.mrc"
    commands.append('open #%d %s' % (model_id, path))
    commands.append('move 0,0,%d models #%d' % (particle_height_offset + 25, model_id))
    return model_id


def scale_and_invert_mrc(filename):
    mrcfile.validate(filename)
    data = np.array([])
    val_range = 0
    min_val = 0
    with mrcfile.open(filename, mode='r', permissive=True) as mrc:
        val_range = mrc.header.dmax - mrc.header.dmin
        min_val = mrc.header.dmin
        # mrc.data *= -1
        # mrc.data += val_range
        data = np.copy(mrc.data)

    new_file = os.path.dirname(filename) + "/" + \
               os.path.splitext(os.path.basename(filename))[0] + "_inverted.mrc"

    # print(new_file)
    with mrcfile.new(new_file, overwrite=True) as mrc:
        data *= -1
        data += val_range + min_val
        mrc.set_data(data)
        mrc.voxel_size = 2.83


def simulate_tiltseries(port, simulation, source="", save_to=""):
    commands = []
    model_id = 0

    output_filename = simulation.particle_map_file

    # Assign random angle of particle with respect to membrane
    # TODO: Make each particle in a set have a different angle
    # angles = []
    # for i in range(simulation.particles_per_stack):
    #     angles.append(random.gauss(0, 5))
    # simulation.extend_angles(angles)
    simulation.add_angle(random.gauss(0, 5))

    # Assign random orientation within tiltseries
    tbl_file = "/data/kshin/T4SS_sim/manual_full.tbl"
    orientations_distribution = tem_utils.load_tbl_file_orientations(tbl_file)

    random_orientations = tem_utils.modify_sim_input_files(simulation, orientations_distribution)
    simulation.extend_orientations(random_orientations)

    metadata_queue.put(simulation.to_json())
    # Generate base model
    # model = pt.make_two_barrels(model_id, commands)

    model = chimera.load_model_from_source(source, model_id, commands)
    # barrel_source = "/data/kshin/T4SS_sim/barrel_high.mrc"
    # rod_source = "/data/kshin/T4SS_sim/single_rod.mrc"
    # model = pt.make_symmetric_rods(model_id, commands, 4, barrel_source=barrel_source, rod_source=rod_source)

    # model = pt.make_gold_bead(model_id, commands)

    # Save base particle
    if save_to != "":
        commands.append("volume #%d save %s" % (model, save_to))

    # Apply random rotation and position
    # TODO Move random position and angle into custom assembler
    position = get_random_position()
    commands.append("move %.2f,%.2f,0 models #%d" % (position[0], position[1], model))
    angle = simulation.angles[0]
    commands.append("turn y %.2f models #%d" % (angle, model))

    # Tack on membrane
    particle_height_offset = 75
    membrane_model = open_membrane(commands, 100, particle_height_offset)

    # Commands to combine membrane and particle into one mrc
    final_model = 99
    commands.append("vop add #%d,#%d modelId #%d" % (membrane_model, model, final_model))

    # Turn the entire model to get side views
    commands.append("turn x -90 models $%d" % final_model)

    # Save truth particle map
    commands.append("volume #%d save %s" % (final_model, output_filename))
    # commands.append("volume #%d save %s"%(model_id, output_filename))

    base_request = 'http://localhost:%d/run' % (int(port))
    # Run the Chimera commands
    print("Making simulated map using Chimera...")
    for c in commands:
        # log(simulation.log_file, "Making request: " + c)
        r = requests.get(base_request, params={'command': c})
        # log(simulation.log_file, "Response:")
        # log(simulation.log_file, r.text)

    # Clean up
    # log(simulation.log_file, "Cleaning up Chimera")
    requests.get(base_request, params={'command': 'close session'})

    tem_utils.run_tem_simulator(simulation)

    print("Inverting final mrc: %s" % simulation.tiltseries_file)
    scale_and_invert_mrc(simulation.tiltseries_file)


def run_process(args, pid):
    keep_temps = args.keep_tmp
    chimera_process, port = chimera.start_chimera_server()

    root = args.root
    raw_data_dir = root + "/raw_data"

    project_name = args.name
    if project_name is None:
        project_name = os.path.basename(root)

    # TODO Each gets a temp dir for TEM files, keep track of metadata; compiled at end
    process_temp_dir = root + "/temp_%d" % pid

    # Copy over TEM-Simulator input files so it doesn't interfere with
    # any other potentially running simulations
    new_coord_file = process_temp_dir + "/T4SS_coord.txt"
    new_input_file = process_temp_dir + "/sim.txt"
    copyfile(args.coord, new_coord_file)
    copyfile(args.config, new_input_file)
    coordinates_file = new_coord_file
    sim_input_file = new_input_file

    # One overall log file for the simulation
    # log_file = simulated_data_dir + "/sim_%s_%d.log" % (sim_type, run_number)
    metadata_file = process_temp_dir + "/metadata_%d.log" % pid

    # Set up array of metadata for each set of particles
    # log(metadata_file, "[")

    num_stacks = args.num_stacks / args.num_cores
    # If last core, tack on the remainder stacks as well
    if pid == args.num_cores - 1:
        num_stacks += args.num_stacks % args.num_cores

    for i in range(num_stacks):
        log_msg = "Simulating %d of %d tilt stacks assigned to CPU #%d" % (
            i + 1, num_stacks, pid)
        print(log_msg)
        # log(log_file, log_msg)

        global_id = pid * num_stacks + i
        stack_dir = raw_data_dir + "/%s_%d" % (project_name, global_id)

        true_map_file = process_temp_dir + "/%s_%d_truth.mrc" % (project_name, global_id)
        tiltseries_file = stack_dir + "/%s_%d.mrc" % (project_name, global_id)
        nonoise_tilts_file = stack_dir + "/%s_%d_nonoise.mrc" % (project_name, global_id)
        sim = Simulation(coordinates_file, sim_input_file, metadata_file,
                         true_map_file, tiltseries_file, nonoise_tilts_file, keep_temps=keep_temps)

        # saved_particle = "/data/kshin/T4SS_sim/c4_particle_light.mrc"
        simulate_tiltseries(port, sim, source=args.model)

        # if i != num_particle_sets - 1:
        #     log(metadata_file, ",")

    # Close Chimera for good
    chimera_process.terminate()

    # Clean up temp files if desired
    if not keep_temps:
        rmtree(process_temp_dir)


def main():

    args = parse_inputs()

    send_notification = False
    if args.email != '':
        send_notification = True

    start_time = time.time()

    # Set up simulation file directories

    # Trailing slash not expected by rest of program
    args.root = args.root.rstrip("/")

    # run_number = get_available_data_dir_num(root)
    # true_data_dir = root + "true_volumes_%d" % run_number
    # simulated_data_dir = root + "simulated_tiltseries_%d" % run_number

    raw_data_dir = args.root + "/raw_data"
    os.mkdir(raw_data_dir)

    # os.mkdir(true_data_dir)
    # os.mkdir(simulated_data_dir)

    # Set up parallel processes
    num_cores = args.num_cores
    if num_cores is None:
        num_cores = multiprocessing.cpu_count()

    # TODO Everything below prob gets put in processes
    processes = []
    for i in range(num_cores):
        process = multiprocessing.Process(target=run_process, args=(args, i))
        processes.append(process)
        process.start()

    for process in processes:
        process.join()

    time_taken = (time.time() - start_time) / 60.
    # log(sim.log_file, 'Total time taken: %0.3f minutes' % time_taken)
    # log(metadata_file, "]")

    # Metadata objects for each stack
    metadata = []
    while not metadata_queue.empty():
        metadata.append(metadata_queue.get())
    metadata_file = args.root + "/sim_metadata.log"
    with open(metadata_file, 'w') as f:
        f.write(json.dumps(metadata, indent=4))

    if send_notification:
        send_email("kshin@umbriel.jensen.caltech.edu", args.email,
                   "Simulation complete", 'Total time taken: %0.3f minutes' % time_taken)
