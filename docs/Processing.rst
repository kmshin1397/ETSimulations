Processing
==========

============
Introduction
============

Automatic processing of simulated data sets using the ETSimulations software revolves around **"Processors"**. Each Processor is a module of the software designed to facilitate processing of simulated data sets. Currently, the **EMAN2 Processor** and the **IMOD Processor** are available. As each software has differing project structure and workflows, the exact behavior of each processor will be quite different and personalized to each software. However, setting up and running any processor will always revolve around the **ets\_process\_data.py** program. Here as well, we provide input via a configuration YAML file.

The YAML file provided to the ets\_process\_data.py run should have:

    * **root** : string
        The path to the folder which contains the raw\_data and sim\_metadata.json files created by ets\_generate\_data.py
    * **name** : string
        The project name - should be the same one used for the simulations
    * **processors** : list of strings
        A list of processor objects which have a "name" and "args" arguments. The specifics to what goes into these fields can be found in more details in the section of the manual particular to that processor.


To run the processor module (assuming a YAML file called processor\_configs.yaml), run: ::

    python src/ets_process_data.py -i processor_configs.yaml

====================
Available processors
====================

.. toctree::
    EMAN2Processor
    IMODProcessor
    I3Processor
