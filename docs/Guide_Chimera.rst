.. _guide-chimera:

Particle assembly using Chimera
===============================

`UCSF Chimera <https://www.cgl.ucsf.edu/chimera/>`_ is the recommended tool to use to build up your source particles/complexes to be inserted into your simulated cryo-ET data. While any .mrc source density map created in some manner will theoretically work if simply using the **use\_common\_model** option with the :ref:`Basic Assembler <tutorial-basic-assembler>`, any further heterogeneity you wish to include in your simulated data sets will require interaction through Chimera.

ETSimulations leverages the commands available through the `Chimera Command Line <chimeracommandslink>`_ to assemble and apply any desired perturbations to individual particles within a data set, communicating with Chimera instances spawned as `REST servers <chimeraserverlink>`_. Thus, it is a good idea to get familiar with the Chimera commands available to manipulate PDB models and density maps to not only assemble your initial template particle density map, but to later be able to customize your simulated data sets to include various heterogeneity strategies such as random rotations of specific segments in your particle.

Let us say you wish to generated simulations of some biological complex by putting together a number of PDB models as segments of the structure. PDB models provide a good starting point with biologically accurate structure, but can be prohibitively slow further down the pipeline to simulate over and over especially if your complex includes large pieces like a membrane section. Thus, the first step you should probably take is to open your PDB models in Chimera and run the "molmap" command on them to save your individual PDB pieces as MRC density maps. Note that these density maps will be used to generate tiltseries and eventually sub-tomogram averages and the resolution you create the density maps to from the PDBs here will act as the theoretical resolution limit to your final sub-tomogram averages.

Once you have MRC versions of your PDB pieces, you are ready to begin assembling your complex.