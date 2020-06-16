.. _tutorial-basic-assembler:

Simple simulations with the Basic Assembler
===========================================

Introduction
------------

The most straightforward simulation targets will require little variation among individual particles within a data set; in this case the included Basic Assembler can be used to quickly get to your simulated data without putting together an entire custom Assembler class.

The Basic Assembler implements a minimal assembler class designed to support simulation of data sets that don't require variable Chimera commands among different particles, using a shared pre-compiled source particle. For example, the more complicated T4SS Assembler example adds heterogeneity through things like randomized rotations and shifts for each particle. This means that each particle simulated for the T4SS workflow must be reassembled in Chimera to incorporate randomly generated angles and shifts. However, if all that is required is to use a consistent density map as the particles to simulate into tilt stacks we can skip a lot of the complexity and that is where the Basic Assembler comes in.

Putting together the particle map
---------------------------------

Minimally, all that is required to be passed along to the Basic Assembler is a density map (in .mrc format) or a PDB file representing the particle you wish to insert into your simulated tiltseries. If you require putting together multiple MRC or PDB pieces together into a simulated complex for this source map, it is recommended to do so within Chimera using its Command Line commands. Technically any method you wish to use to come to an MRC or PDB input is viable. But if in the future you decide to expand your simulations to incorporate heterogeneity like with the T4SS Assembler described above, it will be useful to have Chimera commands already worked out for your particle assembly.

For tips on using Chimera to assemble particles, refer to :ref:`the Chimera guide <guide-chimera>`.

Setting up the simulation run
-----------------------------

Once you have a particle source file to use for your simulation, it is time to set up the run of **ets\_generate\_data.py**. You need to make a .yaml configuration file to pass in to the data generation program, much like the example provided as **configs.yaml**. The specific parameters are described :ref:`here <ets-generate-data-params>`. The **model** parameter should hold the full file path to your particle source file. The **assembler** parameter should be set to "basic" since we are using the Basic Assembler. Finally, take note of the **custom\_configs** parameter. The custom\_configs object is used to pass along any Assembler-specific arguments to the particle assembler. For the Basic Assembler, there is a single custom configuration option available - the **use_common_model** option.

use\_common\_model
``````````````````
The **use\_common\_model** is incorporated into your YAML configurations like so: ::

    ... # Other configurations

    custom_configs:
        use_common_model: true

Enable this option to just use the same particle model source file for every instance of the particle within the generated data set (given by the **model** parameter).

If this option is turned off, ETSimulations will instead open the source file in Chimera and save a duplicate of it to temporary files for each particle to be put into the simulations. This approach is exposed to allow users to add in some of their own Chimera commands between opening and saving the temporary copy of the particle if they wish to manipulate them somehow. To add in some of your own Chimera commands, you need to edit the assemblers/basic\_assembler.py file.

Specifically, the **__assemble_particle()** function starting on line 50 is where the Chimera commands are defined. You will see that out of the box, the only commands are to open and save the model file before clearing the Chimera session for the next particle. This is where you would insert your own commands with the same "self.commands.append()" structure. For example, if you wanted to apply a small random rotation about the x-axis for every particle, that code segment could be changed to:

.. code-block:: python
    :linenos:
    :lineno-start: 59
    :emphasize-lines:  4,5

    # The first Chimera command is to open the template model file
    self.commands.append("open #%d %s" % (model_id, self.model))

    # Rotate by a random angle
    self.commands.append("turn x %.3f models #%d" % (random.gauss(0, 5), model_id))

    # Now we just save it to the desired location passed in
    self.commands.append("volume #%d save %s" % (model_id, output_filename))

    # Clear for the next particle
    self.commands.append("close session")

Note: If you are unfamiliar with Python's string formatting, you may want to quickly read up on it to clear up any confusion about the code above.

If you wish to do more extensive customization and manipulation beyond a few quick extra Chimera commands applied to each particle, it is recommended that you go through the :ref:`custom Assembler guide <guide-custom-assembler>` in order to maintain better structure to your modifications.

Running the simulation
----------------------

Once you have the configuration YAML and any modifications to the assembler done, you are ready to run the simulation. As shown in the :ref:`simulation overview section <simulation-overview>`, this can be done by: ::

    python ets_generate_data.py -i <your-YAML-file>

You will see Chimera windows open up (the number of which was specified in your YAML file) and if you have **use\_common\_model** turned to false, you will see models being opened and saved through Chimera as ETSimulations sets up runs of the TEM-Simulator. The maximum number of TEM-Simulator runs that can run concurrently is determined by your **num\_cores** parameter, though the true number may be less at times if processes need to spend time assembling particles through Chimera before running TEM-Simulator.

To keep track of the current progress of the overall data set run in more detail, you can take a look at the <name>.log file located in your project **root** folder.

To check on specific TEM-Simulator runs for each child process (each core is responsible for a child process that handles a number of stacks to generate) you can check out the simulator.log file in the temp_* folders (a temp folder is created for each child process to use).

The outputs
-----------

Running the **ets\_generate_data.py** program will result in a **raw\_data** folder being created in the project directory specified in the configurations. In the **raw\_data** folder, each tiltseries will get its own sub-directory titled {name}\_{stack number}. In each sub-directory, you will find a no-noise version of the stack and a normal noisy version.

Another output of the data generation process is the **sim\_metadata.json** file. This is a JSON file containing metadata like positions of the particles for each tiltseries generated, including any custom metadata you can choose to include by editing your Assembler class. For example, the T4SS Assembler saves the random orientations and random shifts/angles away from the centered/perpendicular positions for each component of the simulated particle which were generated during the run. To add custom metadata to your simulations, the :ref:`Simulation.set\_custom\_data() <docstrings-simulation>` function should be called within the Assembler's set\_up\_tiltseries() function. For example, this is done for the T4SS Assembler in t4ss\_assembler.py : line 398.