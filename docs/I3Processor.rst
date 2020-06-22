The I3 Processor
==================
The I3 Processor, found in processors/i3\_processor.py, is implemented to facilitate processing of the generated simulation dataset with the `I3 software <i3link>`_. Specifically, a project directory is created and set up, along with necessary files, for running sub-tomogram averaging using I3.

The previous steps of aligning, reconstructing, and particle-picking is not handled by I3 and must be done with another software. The I3 Processor can currently take the results of the :ref:`IMOD Processor <imod_processor>` to set up the I3 run, and support for the :ref:`EMAN2 Processor <eman2_processor>` output is planned for future work.

The IMOD Processor as well will take its inputs from the configuration YAML passed into ets\_process\_data.py. The following is an example of minimal I3 configurations: ::

    processors: [
      {
        name: "i3",
        args: {
          mraparam_path: "",
          real_data_mode: false,
          tlt_angle: -90.0
        }
      }
    ]

==========
Parameters
==========
The I3 Processor, like all others, have the **name** argument ("i3") and an **args** object filled with parameters. The only required parameters are a file path to the mraparam.sh file to use and the real\_data\_mode option. There are a number of further parameters that must be provided if enabling the real\_data\_mode, as we cannot assume specific directory/file naming patterns like we can with the simulated data known to have gone through the IMOD Processor.

Specifically, we have:

    * **mraparam\_path** : string
        A file path to a mraparam.sh file to be copied in to the newly created I3 project directory

    * **real\_data\_mode** : bool
        Enable this to let the I3 Processor know that you are processing real data and to use the other parameters below rather than assuming the directory/file naming patterns used by IMOD Processor.

    * **tlt\_angle** : float
        The tilt angle for the maps to record in the generated .tlt files for missing-wedge compensation

    * **imod\_dir** : string
        (Required only if **real\_data\_mode** is set to true) The IMOD project directory to transfer to an I3 project

    * **i3\_dir** : string
        (Required only if **real\_data\_mode** is set to true) The destination directory to create the I3 project in

    * **dir_contains** : string
        (Required only if **real\_data\_mode** is set to true) When iterating through the IMOD directory, take only the sub-directories containing this string as tomogram data directories to import into I3

    * **rec_contains** : string
        (Required only if **real\_data\_mode** is set to true) When looking for the tomogram reconstruction file in a directory, look for .mrc or .rec files containing this string

    * **mod_contains** : string
        (Required only if **real\_data\_mode** is set to true) When looking for the particle MOD file in a directory, look for .mod files containing this string

    * **tlt_contains** : string
        (Required only if **real\_data\_mode** is set to true) When looking for the .tlt file in a data directory, look for .tlt files containing this string. Note that standard IMOD processing will produce both "\*\_fid.tlt" and "\*\_.tlt" files; you probably want to use the latter. Thus, this parameter should probably be set to something like "\*.tlt" to exclude the "\*\_fid.tlt" files.


=====================================
Using the I3 Processor on real data
=====================================
It is possible to use the I3 Processor to set up an I3 project on real data processed with IMOD. To do so, something like the processor arguments below could be used (see the list of parameters above for more details): ::

    processors: [
      {
        name: "i3",
        args: {
          mraparam_path: "path/to/mraparam.sh",
          real_data_mode: true,
          tlt_angle: 85.7,
          imod_dir: "path/to/imod/project/directory",
          i3_dir: "path/to/new/i3/project/directory",
          dir_contains: "project_name",
          rec_contains: "name_SIRT_1k",
          mod_contains: "particle_name.mod",
          tlt_contains: "project_name.tlt"
        }
      }
    ]

When interacting with the Processor in this manner, the **root** parameter in the YAML configs passed to ets\_process\_data.py doesn't matter (since we don't have a ets\_generate\_data.py project root folder to look to for retrieving knowing orientations, etc.) and is ignored. However, the **name** parameter is still used as the particle name to use when apt. For the I3 Processor specifically, this name is tacked on to set names in the defs/sets file.

Note that the I3 Processor will only do the project set up, such as creating the defs, maps, and trf folders and the defs/maps and defs/sets files. The user must still run *i3avg* on their own and perform manual inspection of classes, etc. as would be involved in normal I3 usage.
