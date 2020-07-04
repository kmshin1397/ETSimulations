.. _dynamo_processor:

The Dynamo Processor
====================
The Dynamo Processor, found in processors/dynamo\_processor.py, is implemented to facilitate setting a sub-tomogram averaging project within Dynamo. Currently, starting from an IMOD project for reconstructions/particle picking is supported.

The Dynamo Processor will first generate a Dynamo-format volume index .doc file and data table .tbl file based on the IMOD source provided. Afterwards, a MATLAB script designed to set up a Dynamo averaging project based on these will be generated and placed in the folder created for the Dynamo run. The generated script will contain code to extract the particles to be averaged and then create a new `Dynamo alignment project <https://wiki.dynamo.biozentrum.unibas.ch/w/index.php/Alignment_project>`_ for them. Various parameters for this project can be provided via the processor args in the YAML file passed to ets\_process\_data.py, and they will be passed along to the generated MATLAB script.

The Dynamo alignment project parameters, and other arguments to the Processor, are listed in the section below.

Required arguments
-------------------
All these are parameters that should be placed in the **args** section of the Processor's YAML configurations.

    * **box_size** : int
        The particle box size

    * **num_workers** : int
        The number of Matlab workers to spawn for the particle cropping and initial averaging functions (the 'mw' parameter for these)

    * **project_name** : string
        A name for the Dynamo project

    * **real\_data\_mode** : bool
        Enable this to let the Dynamo Processor know that you are processing real data and to use the other parameters below rather than assuming the directory/file naming patterns used by IMOD Processor.

    * **dynamo\_dir** : string
        (Required only if **real\_data\_mode** is set to true) The destination directory to create the Dynamo project in

    * **dir\_contains** : string
        (Required only if **real\_data\_mode** is set to true) When iterating through the IMOD directory, take only the sub-directories containing this string as tomogram data directories to import into I3

    * **rec\_contains** : string
        (Required only if **real\_data\_mode** is set to true) When looking for the tomogram reconstruction file in a directory, look for .mrc or .rec files containing this string

    * **mod\_contains** : string
        (Required only if **real\_data\_mode** is set to true) When looking for the particle MOD file in a directory, look for .mod files containing this string

    * **tlt\_contains** : string
        (Required only if **real\_data\_mode** is set to true) When looking for the .tlt file in a data directory, look for .tlt files containing this string. Note that standard IMOD processing will produce both "\*\_fid.tlt" and "\*\_.tlt" files; you probably want to use the latter. Thus, this parameter should probably be set to something like "\*.tlt" to exclude the "\*\_fid.tlt" files.

The arguments below are used for the Dynamo alignment project specifically, and assigned in the generated script using the *dvput* function. Descriptions for these parameters can be found through the Dynamo `dcp GUI <https://wiki.dynamo.biozentrum.unibas.ch/w/index.php/Dcp_GUI>`_.

    * **cores** : int

    * **mask** : string

    * **mwa** : int

    * **ite_r1** : int

    * **cr_r1** : int

    * **cs_r1** : int

    * **ir_r1** : int

    * **is_r1** : int

    * **rff_r1** : int

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