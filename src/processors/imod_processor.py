import shutil
import csv
import json
import os
from scipy.spatial.transform import Rotation as R
import numpy as np
import sys
from tempfile import mkstemp
import re
import subprocess
import shlex


def retrieve_orientations(metadata_file, root):
    """
    This will put a 'T4SS_slicerAngles.csv' file in each IMOD data sub-directory with the slicer
        angles for particle in that tomogram (in the order of the coordinates defined in the
        input particle coordinates text file to TEM-Simulator, except rotated 90 degrees clockwise
        around the z-axis since the tomogram reconstruction causes such a rotation)

    Args:
        metadata_file: The sim_metadata.json metadata file generated by ets_generate_data.py
        root: The directory in which the tomogram sub-directories are located

    Returns: None

    """
    with open(metadata_file, "r") as f:
        metadata = json.loads(f.read())
        for particle_set in metadata:
            basename = os.path.basename(particle_set["tiltseries_file"]).split(".")[0]
            csv_name = root + "/%s/" % basename + "T4SS_slicerAngles.csv"
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

                    # rotate around x by -90 to get the side view
                    orientation_mat = np.dot(R.from_euler('zxz', [0, -90, 0],
                                                          degrees=True).as_matrix(),
                                             rotation.as_matrix())

                    rotation = R.from_matrix(orientation_mat)

                    euler = rotation.as_euler('zyx', degrees=True)
                    new_row = [euler[2], euler[1], euler[0]]

                    writer.writerow(new_row)


def replace_adoc_values(adoc_file, imod_args):
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
            new_file.write("runtime.RAPTOR.any.useAlignedStack = 1")
        elif imod_args["fiducial_method"] == "autofidseed":
            new_file.write("runtime.Fiducials.any.trackingMethod = 0")
            new_file.write("runtime.Fiducials.any.seedingMethod = 3\n")

    # Remove original file
    os.remove(adoc_file)
    # Move new file
    shutil.move(abs_path, adoc_file)


def set_up_batchtomo(root, name, imod_args):
    """

    Args:
        root:
        name:
        imod_args:

    Returns: The newly created IMOD .com file to run the batchtomo

    """
    # Set up an IMOD project directory
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
        if base.startswith("T4SS"):
            print(base)
            new_tilt_folder = imod_project_dir + "/%s" % base

            os.mkdir(new_tilt_folder)
            raw_stack = base + ".mrc"

            # Copy over stack and relevant intermediate IMOD files
            # We are copying over our own versions of the outputs of coarse alignment in IMOD
            # since we want to skip that step.
            shutil.copyfile(raw_data + "/" + base + "/" + raw_stack,
                            new_tilt_folder + "/" + base + ".mrc")
            shutil.copyfile(raw_data + "/" + base + "/" + raw_stack,
                            new_tilt_folder + "/" + base + ".preali")
            for template_file in os.listdir(template_path):
                template = os.fsdecode(template_file)

                # Copy over all the IMOD coarse alignment files so that we can fake that we've done
                # it and can skip it. These are the .prexf, .prexg, and .rawtlt files.
                if not template.endswith(".txt") and not template.startswith("batchtomo_files"):
                    ext = os.path.splitext(template)[1]
                    shutil.copyfile(template_path + "/" + template,
                                    new_tilt_folder + "/" + base + ext)

    print("Retrieving directories..")
    retrieve_orientations(root + "/sim_metadata.json", imod_project_dir)

    # Copy over batchtomo files
    batchtomo_name = "batchETSimulations"

    # Copy over the adoc file and write in the passed in values
    main_adoc = "%s/%s.adoc" % (batchtomo_templates, batchtomo_name)
    new_main_adoc = imod_project_dir + "/%s.adoc" % batchtomo_name

    if "custom_batchruntomo_template" in imod_args:
        shutil.copyfile(imod_args["custom_batchruntomo_template"], new_main_adoc)
    else:
        shutil.copyfile(main_adoc, new_main_adoc)
        replace_adoc_values(new_main_adoc, imod_args)

    print("Copying in batchtomo files")
    directory = os.fsencode(imod_project_dir)
    batchtomo_infos = []
    for base_folder in os.listdir(directory):
        base = os.fsdecode(base_folder)
        if base.startswith(name):

            # Copy over individual sub-directory adoc files
            batch_file = ("%s_name.adoc" % batchtomo_name).replace("name", base)
            this_adoc = "%s/%s/%s" % (imod_project_dir, base, batch_file)
            shutil.copyfile(new_main_adoc, this_adoc)

            # Look for stack
            stack = ""
            for file in os.listdir(os.fsencode("%s/%s" % (imod_project_dir, base))):
                filename = os.fsdecode(file)
                if filename.endswith(".mrc"):
                    stack = filename
                    break

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


def imod_main(root, name, imod_args):
    """ The method to set-up tiltseries processing using IMOD

    The steps taken are:
    1. Make IMOD dir
    2. Copy over template batchtomo files, as well as IMOD coarse alignment files (simulated data
        will not have enough signal usually to work well with the template-matching coarse alignment
        step, so we need to skip and fake that step)
    3. Fill in the specific parameters for the batchtomo files based on the passed in arguments

    Returns: None

    """

    start = imod_args["start_step"]
    end = imod_args["end_step"]
    com_file = "%s/%s.com" % (root + "/processed_data/IMOD", "batchETSimulations")
    if end <= start:
        print("ERROR: The batchruntomo ending step is less than or equal to the starting step")
        exit(1)
    elif start == 0:
        set_up_batchtomo(root, name, imod_args)
        # First run batchruntomo with just the set up step and stop before it does the coarse
        # alignment
        if os.getenv("IMOD_DIR") is not None:
            submfg_path = os.path.join(os.environ["IMOD_DIR"], "bin", "submfg")
            command = "%s -t %s" % (submfg_path, com_file)
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
        else:
            print('ERROR: IMOD_DIR is not defined')
            exit(1)

        # Now set it up to resume after the coarse alignment
        replace_batchtomo_start_and_end_steps(com_file, 4, end)
    else:
        if start == 2 or start == 3:
            print("WARNING: cross-correlation alignment will most likely fail due to low signal of "
                  "simulated stacks")
        replace_batchtomo_start_and_end_steps(com_file, start, end)

    # Now run batchruntomo up to the desired end step, having avoided cross-correlation by default
    if os.getenv("IMOD_DIR") is not None:
        submfg_path = os.path.join(os.environ["IMOD_DIR"], "bin", "submfg")
        command = "%s -t %s" % (submfg_path, com_file)
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
    else:
        print('ERROR: IMOD_DIR is not defined')
        exit(1)
