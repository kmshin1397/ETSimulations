.. _artiatomi_processor:

The Artiatomi Processor
=======================

Introduction
------------

The Artiatomi Processor attempts to help along processing of data with the `Artiatomi software <https://github.com/uermel/Artiatomi>`_. It assumes that you have a working set of the Artiatomi command line tools (either built from the source or through the `Artiatomi Docker image <https://github.com/kmshin1397/artiatomi-tools>`_).

As the standard Artiatomi workflow generally involves Matlab driver scripts along with calling the Artiatomi command line tools where needed, the Artiatomi Processor mainly attempts to generate these Matlab scripts for the user to run.

The Artiatomi Processor must start with an IMOD project (either simulated or real data) that has at least gone through the tiltseries alignment process. This is because while Artiatomi does provide its own bead tracking and alignment workflow (through the Clicker tool) there is no automatic alignment native to Artiatomi and for the streamlined processing ETSimulations is designed for, we would like to take advantage of the automatic alignment provided through IMOD.

As with any of the other processors, parameters are provided in a YAML file fed into the ets\_process\_data.py program. The parameters taken are discussed below.

A note on EMAN2
^^^^^^^^^^^^^^^
EMAN2 source projects are unfortunately not supported at this time. EMAN2 uses significantly different alignment parameters from IMOD and Artiatomi, so it is challenging to support doing Artiatomi's EmSART reconstruction based off of EMAN2 aligned stacks.

It is possible to use particles extracted from EMAN2 and perform sub-tomogram averaging on them using Artiatomi's SubTomogramAverageMPI. However, this is not supported by the Artiatomi Processor either because SubTomogramAverageMPI is functionally equivalent to performing the STA on EMAN2 particles through Dynamo (supported in the Dynamo Processor). The distinguishing factor of Artiatomi's sub-tomogram processing is the local refinement step which can be performed after the STA step, but this requires the original tiltseries and alignment parameters in the Artiatomi format which we are unable to retrieve when starting from EMAN2 projects. Thus, the decision was made to forgo EMAN2 importation with the Artiatomi Processor for now.


Parameters
----------

The Artiatomi Processor, like all others, have the **name** argument ("artiatomi") and an **args** object filled with parameters. (Remember that the overall YAML file must include a **root** and **name** argument as well)

General parameters
^^^^^^^^^^^^^^^^^^

    * **real_data_mode** : bool
        Enable this to let the Artiatomi Processor know that you are processing real data and to use the other parameters below rather than assuming the directory/file naming patterns used by IMOD Processor.

    * **setup_reconstructions_and_motls** : bool
        Enable this to tell the Artiatomi Processor to generate the necessary scripts to set up reconstructing the tomograms in the project with EmSART and convert either the .mod files (if using real IMOD data) or the recorded simulation metadata (for simulated data) into Artiatomi-format particle motivelists.

    * **setup_averaging** : bool
        Enable this to tell the Artiatomi Processor to generate the script for setting up a run of Artiatomi's SubTomogramAverageMPI for the project.

    * **setup_refinement** : bool
        Enable this to tell the Artiatomi Processor to generate the scripts to be used for the local refinement and re-extraction of particles based on the refined alignments.

Artiatomi-specific parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    * **output_suffix** : string
        A suffix string to attach to the tiltseries base name in order to come up with the EmSART reconstruction output names. For example, a tiltseries called "T4SS_0.st" and an output_suffix of "_SART_HR_1k.em" will result in the final tomogram being named "T4SS_0_SART_HR_1k.em".

    * **tomogram_size_x** : int
        The reconstructed tomogram's size in the X dimension (in number of pixels)

    * **tomogram_size_y** : int
        The reconstructed tomogram's size in the Y dimension (in number of pixels)

    * **tomogram_size_z** : int
        The reconstructed tomogram's size in the Z dimension (in number of pixels)

    * **position_binning** : int
        (Required only for simulated data) The binning factor to apply to the original positions recorded when generating the data so that they match the final tomogram size. For example, if you simulated 2k tiltseries but are reconstructing 1k tomograms, this parameter should be set to 2.

    * **reconstruction_template_config** : string
        A file path to a template EmSART configuration file to use for reconstructing the tomograms in the project. An example for a low-contrast, high-resolution reconstruction is provided in the templates/artiatomi folder. For more information on the configuration file, refer to `the official Artitomi wiki page. <https://github.com/uermel/Artiatomi/wiki/EmSART-%28cfg-file%29>`_

    * **emsart_path** : string
        (Used if setting up reconstructions) The file path to the EmSART compiled executable, if you are working with Artiatomi built from source, or just "EmSART" if it is already on your system's PATH variable. If you are using the Artiatomi Docker image, this can be just set to "EmSART".

    * **emsart_subvols_path** : string
        (Used if setting up refinement) The file path to the EmSARTSubVols compiled executable, if you are working with Artiatomi built from source, or just "EmSARTSubVols" if it is already on your system's PATH variable. If you are using the Artiatomi Docker image, this can be just set to "EmSARTSubVols".

    * **box_size** : int
        (Used in averaging and refinement) The box size for your extracted particles

The following seven parameters are all parameters for the SubTomogramAverageMPI program. Refer to `the Artiatomi wiki page <https://github.com/uermel/Artiatomi/wiki/SubTomogramAverageMPI-%28cfg-file%29>`_ for their details.

    * **angIter** : int

    * **angIncr** : float

    * **phiAngIter** : int

    * **phiAngIncr** : float

    * **lowPass** : int

    * **highPass** : int

    * **sigma** : int

Real data mode parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^
    * **imod_dir** : string
        (Required only if **real\_data\_mode** is set to true) The IMOD project directory to transfer to an Artiatomi project

    * **artia_dir** : string
        (Required only if **real\_data\_mode** is set to true) The destination directory to create the Artiatomi project in

    * **dir_contains** : string
        (Required only if **real\_data\_mode** is set to true) When iterating through the IMOD directory, take only the sub-directories containing this string as tomogram data directories to import into Artiatomi

    * **mod_contains** : string
        (Required only if **real\_data\_mode** is set to true) When looking for the particle MOD file in a directory, look for .mod files containing this string


Example
-------

simulated: ::

    {
      name: "artiatomi",
      args: {
        real_data_mode: false,
        setup_reconstructions_and_motls: true,
        reconstruction_template_config: "/home/kshin/Documents/repositories/ETSimulations/templates/artiatomi/EmSART_HR.cfg",
        output_suffix: "_SART_HR_1k.em",
        tomogram_size_x: 1000,
        tomogram_size_y: 1000,
        tomogram_size_z: 300,
        position_binning: 2
      }
    }


real: ::

    {
      name: "artiatomi",
      args: {
        real_data_mode: true,
        setup_reconstructions_and_motls: true,
        reconstruction_template_config: "/home/kshin/Documents/repositories/ETSimulations/templates/artiatomi/EmSART_HR.cfg",
        output_suffix: "_SART_HR_1k.em",
        tomogram_size_x: 1000,
        tomogram_size_y: 1000,
        imod_dir: "/data/kshin/test",
        artia_dir: "/data/kshin/test/Artia",
        dir_starts_with: "dg",
        mod_contains: "T4SS_YL_2k"
      }
    }


**NOTE** More documentation coming with further details and warnings for each part of the processing