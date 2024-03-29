.. _dynamo_processor:

The Dynamo Processor
====================
The Dynamo Processor, found in processors/dynamo\_processor.py, is implemented to facilitate setting a sub-tomogram averaging project within Dynamo. Currently, starting from an IMOD or EMAN2 project for reconstructions/particle picking is supported.

The Dynamo Processor will first generate a Dynamo-format volume index .doc file and data table .tbl file based on the IMOD/EMAN2 source provided. Afterwards, a MATLAB script designed to set up a Dynamo averaging project based on these will be generated and placed in the folder created for the Dynamo run. The generated script will contain code to extract the particles to be averaged and then create a new `Dynamo alignment project <https://wiki.dynamo.biozentrum.unibas.ch/w/index.php/Alignment_project>`_ for them. The script also includes code for generating an FSC curve using the newly created alignment project. Various parameters for this project can be provided via the processor args in the YAML file passed to ets\_process\_data.py, and they will be passed along to the generated MATLAB script.

The Dynamo alignment project parameters, and other arguments to the Processor, are listed in the section below.

Required arguments
-------------------
All these are parameters that should be placed in the **args** section of the Processor's YAML configurations.

    * **box_size** : int
        The particle box size to crop out Dynamo particles for

    * **num_workers** : int
        The number of Matlab workers to spawn for the particle cropping and initial averaging functions (the 'mw' parameter for these). This will also be used as the **mwa** parameter in the Dynamo alignment project.

    * **project_name** : string
        A name for the Dynamo project

    * **source_type** : string
        The source software from which to import into an Dynamo project. This should be "imod" or "eman2".

    * **real\_data\_mode** : bool
        Enable this to let the Dynamo Processor know that you are processing real data and to use the other parameters below rather than assuming the directory/file naming patterns used by IMOD Processor.

    * **rotx** : bool
        (Should be set to True if converting EMAN2 project with data from the T4SS Assembler) The EMAN2 Processor to Dynamo conversion takes the orientations directly from the simulation metadata. The T4SS Assembler stores its orientations as rotated -90 degrees around the x-axis from what is taken from Dynamo and put into the TEM-Simulator due to the fact that 3dmod has a different symmetry axis and we want side-views of the particles in Slicer; so we reverse it by enabling this option. This is unnecessary for IMOD to Dynamo conversion as we take the orientations from the Slicer angles and can assume the difference in symmetry axis.

    * **imod\_dir** : string
        (Required only if **real\_data\_mode** is set to true and **source\_type** is "imod") The IMOD project directory to transfer to an Dynamo project

    * **dynamo\_dir** : string
        (Required only if **real\_data\_mode** is set to true) The destination directory to create the Dynamo project in

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

    * **apix** : float
        APIX values used for calculating the FSC

The arguments below are used for the Dynamo alignment project specifically, and assigned in the generated script using the *dvput* function. Descriptions for these parameters can be found through the Dynamo `dcp GUI <https://wiki.dynamo.biozentrum.unibas.ch/w/index.php/Dcp_GUI>`_.

    * **cores** : int

    * **mask** : string

    * **ite_r1** : int

    * **cr_r1** : flaot

    * **cs_r1** : float

    * **ir_r1** : float

    * **is_r1** : float

    * **rff_r1** : float

    * **rf_r1** : int

    * **dim_r1** : int

    * **lim_r1** : list of ints

    * **limm_r1** : int

    * **nref_r1** : int

    * **high_r1** : int

    * **low_r1** : int

    * **sym_r1** : string

    * **dst** : string

    * **gpus** : int


* A note on processing from EMAN2: The **box\_size** parameter specified here is for the Dynamo cropped particles. The EMAN2 extracted particles should have a slightly bigger box size set previously when doing the reconstruction/particle picking with EMAN2. This bigger EMAN2 box size will be automatically retrieved from the EMAN2 info JSON files.

=======================================
Using the Dynamo Processor on real data
=======================================
It is possible to use the Dynamo Processor to set up an Dynamo project on real data processed with either IMOD or EMAN2.

Starting from IMOD
``````````````````
To transfer an IMOD project, something like the processor arguments below could be used (see the list of parameters above for more details): ::

    processors: [
      {
        name: "dynamo",
        args: {
          box_size: 64,
          num_workers: 12,
          project_name: "demo",
          real_data_mode: true,
          source_type: "imod",
          imod_dir: "path/to/imod/project/directory",
          dynamo_dir: "path/to/new/dynamo/project/directory",
          dir_contains: "project_name",
          rec_contains: "name_SIRT_1k",
          mod_contains: "particle_name.mod",
          tlt_contains: "project_name.tlt",
          ... # The rest of the Dynamo alignment project options
        }
      }
    ]

Note that the Dynamo Processor will only assist in the project set up, such as creating the data table and alignment project. The user must still run the alignment through Dynamo themselves as with a regular Dynamo workflow.

Starting from EMAN2
```````````````````
To transfer an EMAN2 project, something like the processor arguments below could be used (see the list of parameters above for more details): ::

    processors: [
      {
        name: "dynamo",
        args: {
          box_size: 64,
          num_workers: 12,
          project_name: "demo",
          real_data_mode: true,
          source_type: "eman2",
          eman2_dir: "path/to/eman2/project/directory",
          dynamo_dir: "path/to/new/dynamo/project/directory",
          params_json: "path/to/eman2/project/directory/spt_00/particle_parms_1.json"
        }
      }
    ]

Note that some amount of sub-tomogram averaging should be done already using EMAN2 (at minimum the "generate initial reference" step) in order to have some initial orientation information to write out to the Dynamo data table. The Dynamo Processor also sets up Dynamo to average extracted sub-volumes from EMAN2 (treating each particle as one "tomogram") as EMAN2 reconstruction usually is 1) not CTF corrected 2) binned to 1k*1k for visualization 3) may contain artifacts because it does the reconstruction piece by piece.
