The I3 Processor
==================
The I3 Processor, found in processors/i3\_processor.py, is implemented to facilitate processing of the generated simulation dataset with the `I3 software <i3link>`_. Specifically, a project directory is created and set up, along with necessary files, for running sub-tomogram averaging using I3.

The previous steps of aligning, reconstructing, and particle-picking is not handled by I3 and must be done with another software. The I3 Processor can currently take the results of the :ref:`IMOD Processor <imod_processor>` and the :ref:`EMAN2 Processor <eman2_processor>` to set up the I3 run.

The I3 Processor as well will take its inputs from the configuration YAML passed into ets\_process\_data.py. The following is an example of minimal I3 configurations: ::

    processors: [
      {
        name: "i3",
        args: {
          mraparam_path: "",
          real_data_mode: false,
          tlt_angle: -90.0,
          source_type: "imod"
        }
      }
    ]

==========
Parameters
==========
The I3 Processor, like all others, have the **name** argument ("i3") and an **args** object filled with parameters. The only required parameters are a file path to the mraparam.sh file to use and the real\_data\_mode option. There are a number of further parameters that must be provided if enabling the real\_data\_mode, as we cannot assume specific directory/file naming patterns like we can with the simulated data known to have gone through the IMOD Processor or EMAN2 Processor. If processing simulated data, you must have all reconstructions complete with the IMOD Processor, or have gone through at least the "build_sets" step with the EMAN2 Processor. Starting from real IMOD data, you must have reconstructions complete and particles picked using 3dmod Slicer and saved in .mod files. Starting from real EMAN2 data, you must have at least gone through the workflow enough to have a particles_parms_*.json file from an spt iteration of some sorts.
Specifically, we have:

    * **mraparam\_path** : string
        A file path to a mraparam.sh file to be copied in to the newly created I3 project directory

    * **real\_data\_mode** : bool
        Enable this to let the I3 Processor know that you are processing real data and to use the other parameters below rather than assuming the directory/file naming patterns used by IMOD Processor.

    * **tlt\_angle** : float
        (Required only if **source\_type** is "imod") The tilt axis angle for the maps to record in the generated .tlt files for missing-wedge compensation. For EMAN2 source, the tilt axis angle will be taken from the tomogram info files (as the average across all tilt images) at the same time per-tilt angles are extracted from them for the .tlt file.

    * **source\_type** : string
        The source software from which to import into an I3 project. This should be "imod" or "eman2".

    * **imod\_dir** : string
        (Required only if **real\_data\_mode** is set to true and **source\_type** is "imod") The IMOD project directory to transfer to an I3 project

    * **i3\_dir** : string
        (Required only if **real\_data\_mode** is set to true) The destination directory to create the I3 project in

    * **dir\_contains** : string
        (Required only if **real\_data\_mode** is set to true and **source\_type** is "imod") When iterating through the IMOD directory, take only the sub-directories containing this string as tomogram data directories to import into I3

    * **rec\_contains** : string
        (Required only if **real\_data\_mode** is set to true and **source\_type** is "imod") When looking for the tomogram reconstruction file in a directory, look for .mrc or .rec files containing this string

    * **mod\_contains** : string
        (Required only if **real\_data\_mode** is set to true and **source\_type** is "imod") When looking for the particle MOD file in a directory, look for .mod files containing this string

    * **tlt\_contains** : string
        (Required only if **real\_data\_mode** is set to true and **source\_type** is "imod") When looking for the .tlt file in a data directory, look for .tlt files containing this string. Note that standard IMOD processing will produce both "\*\_fid.tlt" and "\*\_.tlt" files; you probably want to use the latter. Thus, this parameter should probably be set to something like "\*.tlt" to exclude the "\*\_fid.tlt" files.

    * **eman2\_dir** : string
        (Required if **real\_data\_mode** is true and **source\_type** is "eman2") The EMAN2 project directory path.

    * **params\_json** : string
        (Required if **real\_data\_mode** is true and **source\_type** is "eman2") The particle_parms_*.json from a run of EMAN2 spt to retrieve pre-orientations and the particle list from.

===================================
Using the I3 Processor on real data
===================================
It is possible to use the I3 Processor to set up an I3 project on real data processed with either IMOD or EMAN2.

Starting from IMOD
``````````````````
To transfer an IMOD project, something like the processor arguments below could be used (see the list of parameters above for more details): ::

    processors: [
      {
        name: "i3",
        args: {
          mraparam_path: "path/to/mraparam.sh",
          real_data_mode: true,
          tlt_angle: 85.7,
          source_type: "imod",
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

Starting from EMAN2
```````````````````
To transfer an EMAN2 project, something like the processor arguments below could be used (see the list of parameters above for more details): ::

    processors: [
      {
        name: "i3",
        args: {
          mraparam_path: "path/to/mraparam.sh",
          real_data_mode: true,
          source_type: "eman2",
          eman2_dir: "path/to/eman2/project/directory",
          i3_dir: "path/to/new/i3/project/directory",
          params_json: "path/to/eman2/project/directory/spt_00/particle_parms_1.json"
        }
      }
    ]

Note that some amount of sub-tomogram averaging should be done already using EMAN2 (at minimum the "generate initial reference" step) in order to have some initial orientation information to write out to the I3 .trf files. The I3 Processor also sets up I3 to average extracted sub-volumes from EMAN2 (treating each particle as one "tomogram") as EMAN2 reconstruction usually is 1) not CTF corrected 2) binned to 1k*1k for visualization 3) may contain artifacts because it does the reconstruction piece by piece.
