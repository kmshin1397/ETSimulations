.. _guide-chimera:

Particle assembly using Chimera
===============================

`UCSF Chimera <https://www.cgl.ucsf.edu/chimera/>`_ is the recommended tool to use to build up your source particles/complexes to be inserted into your simulated cryo-ET data. While any .mrc source density map created in some manner will theoretically work if simply using the **use\_common\_model** option with the :ref:`Basic Assembler <tutorial-basic-assembler>`, any further heterogeneity you wish to include in your simulated data sets will require interaction through Chimera.

ETSimulations leverages the commands available through the `Chimera Command Line <https://www.cgl.ucsf.edu/chimera/current/docs/UsersGuide/framecommand.html>`_ to assemble and apply any desired perturbations to individual particles within a data set, communicating with Chimera instances spawned as `REST servers <https://www.cgl.ucsf.edu/chimera/current/docs/ContributedSoftware/restserver/restserver.html>`_. Thus, it is a good idea to get familiar with the Chimera commands available to manipulate PDB models and density maps to not only assemble your initial template particle density map, but to later be able to customize your simulated data sets to include various heterogeneity strategies such as random rotations of specific segments in your particle.

Let us say you wish to generated simulations of some biological complex by putting together a number of PDB models as segments of the structure. PDB models provide a good starting point with biologically accurate structure, but can be prohibitively slow further down the pipeline to simulate over and over especially if your complex includes large pieces like a membrane section. Thus, the first step you should probably take is to open your PDB models in Chimera and run the "molmap" command on them to save your individual PDB pieces as MRC density maps. Note that these density maps will be used to generate tiltseries and eventually sub-tomogram averages and the resolution you create the density maps to from the PDBs here will act as the theoretical resolution limit to your final sub-tomogram averages.

Once you have MRC versions of your PDB pieces, you are ready to begin assembling your complex.

Useful commands
---------------

The idea is to open various pieces you want to put together into a complex and rotate/move them into proper position. Here are some commands available in the Chimera Command Line that may be useful:

    * **open** : You will need to use this to bring up the pre-saved MRC maps of the particle pieces into the Chimera session.

    * **move** : Use to translate pieces into place

    * **turn** : Use to apply rotations to pieces

    * **vop** : The "add" and "scale" options are useful for manipulating the volumes. Add can be used to combine multiple pieces into one complete map (likely at the end of your assembly) so that it can be saved as a single particle source map. The scale operation can be used to make certain parts appear darker in the resulting simulated tiltseries.

    * **volume save** : This can be used to save your completed assembled particle map.

General tips
------------

* Distances passed along to the move command will be in Angstroms

* If you find rotations not turning out as you expect them, it is useful to play around with the coordinateSystem parameter for the turn command.

* The Chimera Command Line doesn't seem to support using the Enter key on the number pad of the keyboard, so commands should be executed with the main Enter key.

* Issues with the bounding box of combined assemblies from "vop add" (i.e. the entire particle being tilted) could potentially be addressed with the onGrid option for vop add.

* If you will simply be using the same particle map for all your simulated particles, you can just make the map in Chimera and save it to pass along to ets\_generate\_data.py. However, if you wish to do more advanced customization like randomly rotating certain pieces of the particle throughout the simulation, you will be customizing an Assembler to run these Chimera assembly commands in realtime so you should save the list of Chimera commands used as you explore making your particle maps. 