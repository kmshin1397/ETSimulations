Simulation
==========

============
Introduction
============
The **ets\_generate\_data.py** program is the main entrypoint to creating simulated data sets.

Most all general parameter set up is done through a YAML file which is passed in as an argument to the **ets\_generate\_data.py** program. An example such YAML file is provided in the ETSimulations directory as **configs.yaml**.

Detailed set-up with regards to the characteristics of the particles simulated are controlled through custom **"Assembler"** Python classes which can define a series of Chimera commands to open, manipulate, and combine one or more source maps, i.e. various proteins, into a fake particle source. By default, the example T4SS simulations in the src/assemblers/t4ss\_assembler.py file is set up to be used as the Assembler. Custom arguments to pass along to your custom particle Assemblers can also be defined in the configuration YAML file, as shown in the example. You can refer to the `custom Assembler tutorial`_ for guidance on replacing the T4SS simulations with your own particles.

To actually run a set of simulations, run (assuming you've activated the virtual environment as indicated above - the **source ..** command)::

    python src/ets_generate_data.py -i configs.yaml

More details on the parameters available can be found in the next section.

===================================
Simulation configuration parameters
===================================

As noted above, configuration parameters for simulating data sets with the **ets\_geenrate\_data.py** program relies on a YAML file defining values for various arguments. The specifc options available are listed below.

    * **tem\_simulator\_executable** : string
        The file path to the TEM-simulator executable

    * **chimera\_exec\_path** : string
        The file path to your Chimera installation

    * **model** : string
        The path to the main particle source file (Doesn't actually matter for T4SS simulations because I'm bypassing this and putting together a bunch of different source maps)

    * **root** : string
        The project root directory in which to generate simulations

    * **config** : string
        The TEM-simulator configuration text file to apply to each simulation. An example is provided in the templates folder.

    * **coord** :  string
        TheTEM-simulator particle coordinates text file to use as a reference for placing particles in each generated tiltseries. An example for this is also provided in the templates folder.

    * **num\_stacks** : integer
        The number of tilt stacks to generate

    * **name** : string
        A name for the project

    * **num\_cores** : integer
        The number of parallel cores to utilize

    * **apix** : float
        The pixel size to give to generated stacks, in nm

    * **num\_chimera\_windows** : integer
        The number of Chimera instances to spawn to drive particle assembly. Creating more windows will clutter your display more, but can make simulations run faster. If your particle assembly does not use a lot of Chimera commands/spend a lot of time running Chimera commands, then having multiple Chimera windows may not be necessary

    * **defocus\_values** : List of floats
        A list of defocus values to assign to simulations. The values will be evenly assigned across the dataset, i.e. if 2 defocus values are provided half of the simulated stacks in a dataset will be given one and the other given the other.

    * **bead\_map** : string
        The path to the MRC map representing fake gold beads to scatter throughout the tilt stacks. An example is provided in the templates folder.

    * **email** : string
        An email address to send completion notifications to

===========================
Data set generation outputs
===========================

Running the **ets\_generate_data.py** program will result in a **raw\_data** folder being created in the project directory specified in the configurations. In the **raw\_data** folder, each tiltseries will get its own sub-directory titled {name}\_{stack number}. In each sub-directory, you will find a no-noise version of the stack and a normal noisy version.

The other important output to note is the **sim\_metadata.json** file. This is a JSON file containing metadata for each tiltseries generated, including custom metadata that can be saved from your custom Assembler. For example, the T4SS Assembler saves the random orientations and random shifts/angles away from the centered/perpendicular positions for each component of the simulated particle which were generated during the run. An easy way to interact with and retrieve this information is the Python json module which can load this json as a Python dictionary, i.e. ::

    import json
    metadata = json.load(open("sim_metadata.json", "r"))
