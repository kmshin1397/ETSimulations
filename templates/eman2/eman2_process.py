"""
This script runs a series of EMAN2 processing steps in the order specified in the steps_to_run
variable. The steps_to_run and other parameters for various steps will be filled in dynamically by
the eman2_processor.py module based on the configurations file provided to ets_process_data.py by
the user.

"""
import os
import subprocess
import shlex

# ==================== Input parameters ====================
# General parameters
eman2_root = ""
raw_data_dir = ""
project_name = ""
steps_to_run = ["import", "reconstruct", "extract", "initial_model", "average"]

# Importation parameters
e2import_parameters = {
    "import_tiltseries": "enable",
    "importation": "copy",
    "apix": 1,
    "boxsize": 32
}

# Reconstruction parameters
e2tomogram_parameters = {
    "tltstep": 2,
    "tltax": -90,
    "npk": 10,
    "tltkeep": 0.9,
    "outsize": "1k",
    "niter": "2,1,1,1",
    "pkkeep": 0.9,
    "bxsz": 64,
    "pk_mindist": 0.125,
    "filterto": 0.45,
    "rmbeadthr": 10.0,
    "threads": 48,
    "clipz": 350
}

e2spt_extract_parameters = {
    "alltomograms": "enable",
    "boxsz_unbin": 64,
    "threads": 12,
    "maxtilt": 100,
    "padtwod": 2.0,
    "shrink": 1,
    "tltkeep": 1.0,
    "rmbeadthr": -1.0,
    "alioffset": "0,0,0"
}

e2spt_buildsets_parameters = {
    "allparticles": "enable"
}

e2spt_sgd_parameters = {
    "sym": "c1",
    "gaussz": -1.0,
    "filterto": 0.02,
    "fourier": "enable",
    "batchsize": 12,
    "learnrate": 0.1,
    "niter": 5,
    "nbatch": 10,
    "shrink": 1
}

e2spt_refine_parameters = {
    "niter": 5,
    "sym": "c1",
    "mass": 500,
    "goldstandard": 70,
    "pkeep": 1.0,
    "maxtilt": 90,
    "threads": 12
}


# ==========================================================


def run_process_with_params(base_command, params_dict):
    for arg, value in params_dict.items():
        if value == "enable":
            base_command += " --%s" % arg
        else:
            base_command += " --%s=%s" % (arg, str(value))
        subprocess.run(shlex.split(base_command), check=True)


# ==================== Processing steps ====================
def import_tiltseries():
    # Scan everything in the raw data folder
    for dir_entry in os.scandir(raw_data_dir):
        # For every directory found which begins with the proper project name, i.e. assumed to
        # contain a raw stack
        if dir_entry.is_dir() and dir_entry.name.startswith(project_name):
            stack_basename = dir_entry.name
            stack_to_import = dir_entry.path + "/%s_inverted.mrc" % stack_basename
            base_command = "e2import.py %s" % stack_to_import
            run_process_with_params(base_command, e2import_parameters)


def reconstruct_tomograms():
    # Iterate through each tiltseries
    for tiltseries in os.scandir(os.path.join(eman2_root, "tiltseries")):
        command = "e2tomogram.py %s" % tiltseries
        run_process_with_params(command, e2tomogram_parameters)


def make_particle_set():
    # Extract particles
    base_command = "e2spt_extract.py"
    run_process_with_params(base_command, e2spt_extract_parameters)

    # Build set
    base_command = "e2spt_buildsets.py"
    run_process_with_params(base_command, e2spt_buildsets_parameters)


def make_initial_model(particle_set_file):
    base_command = "e2spt_sgd %s" % particle_set_file
    run_process_with_params(base_command, e2spt_sgd_parameters)


def run_sta(particle_set_file, reference_file):
    base_command = "e2spt_refine.py %s --reference=%s" % (particle_set_file, reference_file)
    run_process_with_params(base_command, e2spt_refine_parameters)


# ==========================================================


# ==================== Main process ====================

functions_table = {
    "import": import_tiltseries,
    "reconstruct": reconstruct_tomograms,
    "extract": make_particle_set,
    "initial_model": make_initial_model,
    "average": run_sta
}


def main():
    # To start, go into EMAN2 project directory
    os.chdir(eman2_root)

    for step in steps_to_run:
        function = functions_table[step]
        function()


if __name__ == '__main__':
    main()
