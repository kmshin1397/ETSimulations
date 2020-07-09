""" This module implements the processing function for the IMOD software package.

The module will create an IMOD project directory and set up a batchruntomo run within it.
"""

import shutil
import csv
import json
import os
from scipy.spatial.transform import Rotation as R
import numpy as np
import sys
from tempfile import mkstemp
import subprocess
import shlex


def retrieve_orientations(metadata_file, name, root):
    """
    This will put a 'T4SS_slicerAngles.csv' file in each IMOD data sub-directory with the slicer
        angles for particle in that tomogram (in the order of the coordinates defined in the
        input particle coordinates text file to TEM-Simulator, except rotated 90 degrees clockwise
        around the z-axis since the tomogram reconstruction causes such a rotation)

    Args:
        metadata_file: The sim_metadata.json metadata file generated by ets_generate_data.py
        name: Particle name
        root: The directory in which the tomogram sub-directories are located

    Returns: None

    """
    with open(metadata_file, "r") as f:
        metadata = json.loads(f.read())
        for particle_set in metadata:
            basename = os.path.basename(particle_set["output"]).split(".")[0]
            csv_name = root + "/%s/" % basename + "%s_slicerAngles.csv" % name
            orientations = np.array(particle_set["orientations"])
            with open(csv_name, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=',',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)

                for i, row in enumerate(orientations):
                    # In ZXZ
                    # ETSimulations gives ref-to-part, external;
                    # rotate by z to account for reconstruction rotation
                    euler = [-row[2] - 90, -row[1], -row[0]] # now at part-to-ref, ext

                    # TEM-Simulator is in stationary zxz
                    rotation = R.from_euler('zxz', euler, degrees=True)

                    # Note: Used to rotate here but have since moved rotations to when recording
                    # the chosen orientations in the T4SS Assembler
                    # rotate around x by -90 to get the side view
                    # orientation_mat = np.dot(R.from_euler('zxz', [0, -90, 0],
                    #                                       degrees=True).as_matrix(),
                    #                          rotation.as_matrix())
                    #
                    # rotation = R.from_matrix(orientation_mat)

                    euler = rotation.as_euler('zyx', degrees=True)
                    new_row = [euler[2], euler[1], euler[0]]

                    writer.writerow(new_row)


def replace_adoc_values(adoc_file, imod_args):
    """
    Helper function to replace certain .adoc values for the batchruntomo run, specifically dealing
        with the fiducial tracking options made available to the ets_process_data.py configs.

    Args:
        adoc_file: The .adoc file path to edi
        imod_args: The dictionary of IMOD Processor arguments

    Returns: None

    """
    # Create temp file
    fh, abs_path = mkstemp()
    with os.fdopen(fh, 'w') as new_file:
        with open(adoc_file) as old_file:
            for line in old_file:
                new_line = line
                if line.startswith("setupset.copyarg.gold"):
                    new_line = "setupset.copyarg.gold = %d\n" % imod_args["num_fiducials"]
                elif line.startswith("comparam.autofidseed.autofidseed.TargetNumberOfBeads"):
                    new_line = "comparam.autofidseed.autofidseed.TargetNumberOfBeads = %d\n" % \
                               imod_args["num_fiducials"]
                elif line.startswith("setupset.copyarg.pixel"):
                    new_line = "setupset.copyarg.pixel = %0.3f\n" % imod_args["apix"]
                elif line.startswith("setupset.copyarg.rotation"):
                    new_line = "setupset.copyarg.rotation = %0.2f\n" % imod_args["tilt_axis"]
                elif line.startswith("runtime.Fiducials.any.trackingMethod"):
                    if imod_args["fiducial_method"] == "raptor":
                        new_line = "runtime.Fiducials.any.trackingMethod = 2\n"
                elif line.startswith("runtime.RAPTOR.any.numberOfMarkers"):
                    new_line = "runtime.RAPTOR.any.numberOfMarkers = %d\n" % \
                               imod_args["num_fiducials"]

                new_file.write(new_line)
        if imod_args["fiducial_method"] == "raptor":
            new_file.write("runtime.Fiducials.any.trackingMethod = 2\n")
            new_file.write("runtime.RAPTOR.any.numberOfMarkers = %d\n" % imod_args["num_fiducials"])
            new_file.write("runtime.RAPTOR.any.useAlignedStack = 1\n")
        elif imod_args["fiducial_method"] == "autofidseed":
            new_file.write("runtime.Fiducials.any.trackingMethod = 0\n")
            new_file.write("runtime.Fiducials.any.seedingMethod = 3\n")

        if imod_args["reconstruction_method"] == "imod-sirt":
            new_file.write("runtime.Reconstruction.any.useSirt = 1\n")

        if "imod_tomogram_thickness" in imod_args:
            new_file.write("comparam.tilt.tilt.THICKNESS = %d\n" %
                           imod_args["imod_tomogram_thickness"])

    # Remove original file
    os.remove(adoc_file)
    # Move new file
    shutil.move(abs_path, adoc_file)


def set_up_batchtomo(root, name, imod_args):
    """ Generates a new set of batchruntomo configuration files in the project directory, such as
        the .com file for the batchruntomo run, the .adoc directive files, and the .ebt Etomo file

    Args:
        root: The ets_generate_data.py project root path
        name: The name of the project
        imod_args: A dictionary of IMOD Processor arguments

    Returns: The newly created IMOD .com file to run the batchruntomo

    """
    # Default values for optional configs
    if "real_data_mode" not in imod_args:
        imod_args["real_data_mode"] = False
    if "data_dirs_start_with" not in imod_args:
        imod_args["data_dirs_start_with"] = name

    # Set up an IMOD project directory
    raw_data = ""
    if imod_args["real_data_mode"]:
        raw_data = root
    else:
        raw_data = root + "/raw_data"

    processed_data_dir = root + "/processed_data"
    imod_project_dir = processed_data_dir + "/IMOD"
    if not os.path.exists(imod_project_dir):
        os.mkdir(imod_project_dir)

    current_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    template = current_dir + "../../templates/imod"
    template_path = os.path.realpath(template)
    batchtomo_templates = template_path + "/batchtomo_files"

    print("Setting up IMOD data directories...")
    directory = os.fsencode(raw_data)
    for base_folder in os.listdir(directory):
        base = os.fsdecode(base_folder)
        if base.startswith(imod_args["data_dirs_start_with"]):
            raw_stack = ""
            new_base = ""
            for f in os.listdir(raw_data + "/" + base):
                # Look for map for the raw stack
                if (f.endswith(".mrc") or f.endswith(".st")) and not f.endswith("nonoise.mrc"):
                    raw_stack = f
                    new_base = os.path.splitext(f)[0]
                    break
            if new_base == "":
                print("ERROR: No .st or .mrc found in %s to use for raw stack" % base)
                exit(1)

            new_tilt_folder = imod_project_dir + "/%s" % new_base
            if not os.path.exists(new_tilt_folder):
                os.mkdir(new_tilt_folder)

            # Copy over stack and relevant intermediate IMOD files
            # We are copying over our own versions of the outputs of coarse alignment in IMOD
            # since we want to skip that step.
            shutil.copyfile(raw_data + "/" + base + "/" + raw_stack,
                            new_tilt_folder + "/" + base + ".mrc")

            # Simulated data needs to skip coarse alignment, so copy over fake outputs for it
            if not imod_args["real_data_mode"]:
                shutil.copyfile(raw_data + "/" + base + "/" + raw_stack,
                                new_tilt_folder + "/" + base + ".preali")

                for template_file in os.listdir(template_path):
                    template = os.fsdecode(template_file)

                    # Copy over all the IMOD coarse alignment files so that we can fake that we've
                    # done it and can skip it. These are the .prexf, .prexg, and .rawtlt files.
                    if template.startswith("name"):
                        ext = os.path.splitext(template)[1]
                        shutil.copyfile(template_path + "/" + template,
                                        new_tilt_folder + "/" + base + ext)

    if not imod_args["real_data_mode"]:
        print("Retrieving orientations...")
        retrieve_orientations(root + "/sim_metadata.json", name, imod_project_dir)

    # Copy over batchtomo files
    batchtomo_name = "batchETSimulations"

    # Copy over the adoc file and write in the passed in values
    main_adoc = "%s/%s.adoc" % (batchtomo_templates, batchtomo_name)
    new_main_adoc = imod_project_dir + "/%s.adoc" % batchtomo_name

    if "custom_template" in imod_args:
        shutil.copyfile(imod_args["custom_template"], new_main_adoc)
    else:
        shutil.copyfile(main_adoc, new_main_adoc)
        replace_adoc_values(new_main_adoc, imod_args)

    print("Copying in batchtomo files...")
    directory = os.fsencode(imod_project_dir)
    batchtomo_infos = []
    for base_folder in os.listdir(directory):
        base = os.fsdecode(base_folder)
        if not base.startswith("batch") and not base.startswith("."):
            # Copy over individual sub-directory adoc files
            batch_file = ("%s_name.adoc" % batchtomo_name).replace("name", base)
            this_adoc = "%s/%s/%s" % (imod_project_dir, base, batch_file)
            shutil.copyfile(new_main_adoc, this_adoc)

            # Look for stack
            stack = ""
            for file in os.listdir(os.fsencode("%s/%s" % (imod_project_dir, base))):
                filename = os.fsdecode(file)
                if filename.endswith(".mrc") or filename.endswith(".st"):
                    # Prioritize .st files over .mrc for when re-processing data that already has
                    # tomogram MRC's inside the folder
                    if stack == "" or filename.endswith(".st"):
                        stack = filename

            batchtomo_info = {"root": stack.split(".")[0],
                              "tilt_folder": "%s/%s" % (imod_project_dir, base), "adoc": this_adoc,
                              "stack": "%s/%s/%s" % (imod_project_dir, base, stack)}
            batchtomo_infos.append(batchtomo_info)

    template_batch_com_file = "%s/%s.com" % (batchtomo_templates, batchtomo_name)
    new_com_file = "%s/%s.com" % (imod_project_dir, batchtomo_name)
    shutil.copyfile(template_batch_com_file, new_com_file)
    with open(new_com_file, "a") as f:
        for info in batchtomo_infos:
            f.writelines(["DirectiveFile    %s\n" % info["adoc"],
                          "RootName    %s\n" % info["root"],
                          "CurrentLocation %s\n" % info["tilt_folder"]])

    template_batch_ebt_file = "%s/%s.ebt" % (batchtomo_templates, batchtomo_name)
    new_ebt = "%s/%s.ebt" % (imod_project_dir, batchtomo_name)
    shutil.copyfile(template_batch_ebt_file, new_ebt)
    with open(new_ebt, "a") as f:
        for i, info in enumerate(batchtomo_infos):
            f.writelines(["meta.row.ebt%d.Run=true\n" % (i + 1),
                          "meta.row.ebt%d.Etomo.Enabled=true\n" % (i + 1),
                          "meta.row.ebt%d.Tomogram.Done=false\n" % (i + 1),
                          "meta.row.ebt%d.RowNumber=%d\n" % (i + 1, i + 1),
                          "meta.row.ebt%d.Log.Enabled=false\n" % (i + 1),
                          "meta.row.ebt%d.Trimvol.Done=false\n" % (i + 1),
                          "meta.row.ebt%d.Rec.Enabled=false\n" % (i + 1),
                          "meta.row.ebt%d.dual=false\n" % (i + 1),
                          "meta.ref.ebt%d=%s\n" % (i + 1, info["stack"])])
        f.write("meta.ref.ebt.lastID=ebt%d\n" % len(batchtomo_infos))


def replace_batchtomo_start_and_end_steps(com_file, start, end):
    """
    Helper function to edit the start and end step parameters in the batchruntomo .com file

    Args:
        com_file: The path to the .com file
        start: The batchruntomo start step
        end: The batchruntom end step

    Returns: None

    """
    # Create temp file
    fh, abs_path = mkstemp()
    with os.fdopen(fh, 'w') as new_file:
        with open(com_file) as old_file:
            for line in old_file:
                new_line = line
                if line.startswith("StartingStep"):
                    new_line = "StartingStep	%0.1f\n" % start
                elif line.startswith("EndingStep"):
                    new_line = "EndingStep	%0.1f\n" % end
                new_file.write(new_line)

    # Remove original file
    os.remove(com_file)
    # Move new file
    shutil.move(abs_path, com_file)


def run_submfg(com_file, cwd=None):
    """
    Helper function to run the IMOD submfg program which runs an IMOD .com file

    Args:
        com_file: The path to the .com file to run
        cwd: The current working directory to run the program under

    Returns: None

    """
    submfg_path = os.path.join(os.environ["IMOD_DIR"], "bin", "submfg")
    command = "%s -t %s" % (submfg_path, com_file)
    print(command)
    if cwd:
        process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, cwd=r"%s" % cwd)
    else:
        process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
    while True:
        output = os.fsdecode(process.stdout.readline())
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
    rc = process.poll()
    if rc != 0:
        exit(1)


def run_tomo3d(tomo3d_path, tlt, tiltseries, output, other_args):
    """
    Helper function to run the tomo3d SIRT reconstruction program

    Args:
        tomo3d_path: The path to tomo3d executable
        tiltseries: The tiltseries to reconstruct
        output: The output reconstruction file path

    Returns: None

    """
    command = "%s -a %s -i %s -o %s" % (tomo3d_path, tlt, tiltseries, output)

    for arg, value in other_args.items():
        if value == "enable":
            command += " -%s" % arg
        else:
            command += " -%s %s" % (arg, str(value))

    print("Running command:")
    print(command)

    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
    while True:
        output = os.fsdecode(process.stdout.readline())
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
    rc = process.poll()
    if rc != 0:
        exit(1)


def run_rotx(input_file, output):
    """
    Helper function to run the IMOD clip rotx program to rotate a tomogram 90 degrees around the
        x-axis

    Args:
        input_file: The path to tomogram to rotate
        output: The path to write the rotated tomogram to

    Returns: None

    """
    clip_path = os.path.join(os.environ["IMOD_DIR"], "bin", "clip")
    command = "%s rotx %s %s" % (clip_path, input_file, output)
    print(command)
    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
    while True:
        output = os.fsdecode(process.stdout.readline())
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
    rc = process.poll()
    if rc != 0:
        exit(1)


def run_flip(input_file, output):
    """
    Helper function to run the IMOD clip flipy program to rotate a tomogram 90 degrees around the
        x-axis

    Args:
        input_file: The path to tomogram to rotate
        output: The path to write the rotated tomogram to

    Returns: None

    """
    clip_path = os.path.join(os.environ["IMOD_DIR"], "bin", "clip")
    command = "%s flipy %s %s" % (clip_path, input_file, output)
    print(command)
    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
    while True:
        output = os.fsdecode(process.stdout.readline())
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
    rc = process.poll()
    if rc != 0:
        exit(1)


def run_binvol(input_file, output, options):
    """
    Helper function to run the IMOD binvol program to bin a tomogram

    Args:
        input_file: The path to tomogram to bin
        output: The path to write the binned tomogram to

    Returns: None

    """
    clip_path = os.path.join(os.environ["IMOD_DIR"], "bin", "binvol")
    command = "%s %s %s" % (clip_path, input_file, output)
    for arg, value in options.items():
        if value == "enable":
            command += " -%s" % arg
        else:
            command += " -%s %s" % (arg, str(value))
    print("Running command:")
    print(command)
    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
    while True:
        output = os.fsdecode(process.stdout.readline())
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
    rc = process.poll()
    if rc != 0:
        exit(1)


def imod_main(root, name, imod_args):
    """ The method to set-up tiltseries processing using IMOD

    The steps taken are:
        1. Make IMOD dir
        2. Copy over template batchruntomo files, as well as IMOD coarse alignment files (simulated
            data will not have enough signal usually to work well with the template-matching coarse
            alignment step, so we need to skip and fake that step)
        3. Fill in the specific parameters for the batchruntomo files based on the passed in
            arguments

    Returns: None

    """

    start = imod_args["start_step"]
    end = imod_args["end_step"]
    com_file = "%s/%s.com" % (root + "/processed_data/IMOD", "batchETSimulations")
    if end <= start:
        print("ERROR: The batchruntomo ending step is less than or equal to the starting step")
        exit(1)
    if os.getenv("IMOD_DIR") is None:
        print('ERROR: IMOD_DIR is not defined as an ENV variable')
        exit(1)

    reconstruct = end >= 14

    # If starting anew, set up batchtomo
    if start == 0:
        set_up_batchtomo(root, name, imod_args)

    # Determine steps to run depending on whether we need to skip coarse alignment or not
    if "force_coarse_align" not in imod_args:
        imod_args["force_coarse_align"] = False

    if imod_args["force_coarse_align"]:
        print("WARNING: cross-correlation alignment will most likely fail due to low signal for "
              "simulated stacks")
        replace_batchtomo_start_and_end_steps(com_file, start, end)

        msg = "Running batchruntomo..."

        # Note: Batchruntomo includes dynamic adjustment of the AngleOffset parameter for tiltalign
        # which we do not want, so we run tiltalign manually and skip step 6
        if start <= 6 <= end:
            # Do up to tiltalign but not including
            if start <= 5:
                print("Running batchruntomo steps up to tiltalign...")
                replace_batchtomo_start_and_end_steps(com_file, start, 5)
                run_submfg(com_file)

            # Manually run each tiltalign using the align.com files in subdirectories
            print("Manually running tiltalign for each stack...")
            imod_proj_dir = root + "/processed_data/IMOD"
            for f in os.listdir(imod_proj_dir):
                # Ignore batchtomo files and go to data dirs
                if not f.startswith("batchETSimulations") and not f.startswith("."):
                    tilt_com = "align.com"
                    run_submfg(tilt_com, cwd=os.path.join(imod_proj_dir, f))

            # Now set main batchtomo com to resume from step 7, up to reconstruction
            if end >= 7:
                replace_batchtomo_start_and_end_steps(com_file, 7, min(end, 13))
                msg = "Running remaining batchruntomo steps up to reconstruction..."

        # Need to run remaining steps if not handled yet above
        if end != 6:
            print(msg)
            run_submfg(com_file)

    else:
        # First run batchruntomo with just the initial steps and stop before it does the coarse
        # alignment
        if start <= 1:
            print("Running initial batchruntomo pre-processing...")
            run_submfg(com_file)

        # Now set it up to resume after the coarse alignment
        if end >= 4:
            replace_batchtomo_start_and_end_steps(com_file, max(4, start), end)
            start = max(4, start)

        # Run remaining steps if there are any
        if end >= 1:
            # Note: Batchruntomo includes dynamic adjustment of the AngleOffset parameter for
            # tiltalign which we do not want, so we run tiltalign manually and skip step 6
            if start <= 6 <= end:
                # Do up to tiltalign but not including
                if start <= 5:
                    print("Running batchruntomo steps up to tiltalign...")
                    replace_batchtomo_start_and_end_steps(com_file, start, 5)
                    run_submfg(com_file)

                # Manually run each tiltalign using the align.com files in subdirectories
                print("Manually running tiltalign for each stack...")
                imod_proj_dir = root + "/processed_data/IMOD"
                for f in os.listdir(imod_proj_dir):
                    # Ignore batchtomo files and go to data dirs
                    if not f.startswith("batchETSimulations") and not f.startswith("."):
                        tilt_com = "align.com"
                        run_submfg(tilt_com, cwd=os.path.join(imod_proj_dir, f))

                # Now set main batchtomo com to resume from step 7, up to reconstruction
                if end >= 7:
                    replace_batchtomo_start_and_end_steps(com_file, 7, min(end, 13))
            # Make sure we don't run reconstruction step before we read what method we want
            else:
                replace_batchtomo_start_and_end_steps(com_file, start, min(end, 13))

            # Need to run remaining steps if not handled yet above
            if end != 6:
                print("Running remaining batchruntomo steps up to reconstruction...")
                run_submfg(com_file)

    # Run reconstruction if necessary
    if reconstruct:
        if imod_args["reconstruction_method"] == "imod-wbp" or \
                imod_args["reconstruction_method"] == "imod-sirt":
            print("Running remaining batchruntomo steps from step 14...")
            replace_batchtomo_start_and_end_steps(com_file, 14, end)
            run_submfg(com_file)

            # If we need to apply rotations or binning to each tomogram, start iterating through the
            # data directories
            if ("rotx" in imod_args and imod_args["rotx"]) or \
                ("binvol" in imod_args and imod_args["binvol"]):
                print("Running tomogram rotations and/or tomogram binning...")
                imod_proj_dir = root + "/processed_data/IMOD"
                for f in os.listdir(imod_proj_dir):
                    # Ignore batchtomo files and go to data dirs
                    if not f.startswith("batchETSimulations") and not f.startswith("."):

                        # Look for tomograms
                        rec_path = ""
                        rec_basename = ""
                        for file in os.listdir(os.path.join(imod_proj_dir, f)):
                            if file.endswith(".rec"):
                                rec_path = os.path.join(imod_proj_dir, f, file)
                                rec_basename = os.path.splitext(file)[0]
                                break

                        if rec_path == "":
                            print("ERROR: Couldn't find reconstruction for directory: %s" % f)
                            exit(1)

                        if "rotx" in imod_args and imod_args["rotx"]:
                            run_rotx(rec_path, rec_path)

                        if "binvol" in imod_args:
                            bin_path = os.path.join(imod_proj_dir, f, "%s_bin%d.mrc" %
                                                (rec_basename, imod_args["binvol"]["binning"]))
                            run_binvol(rec_basename, bin_path, imod_args["binvol"])

        elif imod_args["reconstruction_method"] == "tomo3d":
            print("Running tomo3d reconstructions...")
            imod_proj_dir = root + "/processed_data/IMOD"
            for f in os.listdir(imod_proj_dir):
                # Ignore batchtomo files and go to data dirs
                if not f.startswith("batchETSimulations") and not f.startswith("."):

                    # Look for final aligned tiltseries
                    tiltseries = ""
                    basename = ""
                    tlt = ""
                    for file in os.listdir(os.path.join(imod_proj_dir, f)):
                        if file.endswith(".ali"):
                            tiltseries = os.path.join(imod_proj_dir, f, file)
                            basename = os.path.splitext(file)[0]
                            tlt = os.path.join(imod_proj_dir, f, "%s.tlt" % basename)
                            break

                    if tiltseries == "":
                        print("ERROR: Couldn't find final aligned tiltseries for directory: %s" % f)
                        exit(1)

                    reconstruction_name = "%s_SIRT.mrc" % basename
                    reconstruction_full_path = os.path.join(imod_proj_dir, f, reconstruction_name)
                    run_tomo3d(imod_args["tomo3d_path"], tlt, tiltseries, reconstruction_full_path,
                               imod_args["tomo3d_options"])

                    if "rotx" in imod_args and imod_args["rotx"]:
                        run_rotx(reconstruction_full_path, reconstruction_full_path)

                    if "flipy" in imod_args and imod_args["flipy"]:
                        run_flip(reconstruction_full_path, reconstruction_full_path)

                    if "binvol" in imod_args:
                        bin_path = os.path.join(imod_proj_dir, f, "%s_SIRT_bin%d.mrc" %
                                                (basename, imod_args["binvol"]["binning"]))
                        run_binvol(reconstruction_full_path, bin_path, imod_args["binvol"])

        else:
            print("ERROR: Invalid reconstruction method specified!")
            exit(1)
