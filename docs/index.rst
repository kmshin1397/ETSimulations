Welcome to ETSimulations's documentation!
=========================================

The ETSimulations package is designed to be a tool to the facilitate generation and processing of
simulated cryo-electron tomography data.

* Raw tiltseries are generated with a combination of `UCSF Chimera <https://www.cgl.ucsf.edu/chimera/>`_ and the `TEM-Simulator <http://tem-simulator.sourceforge.net/>`_ package. Simulated particles placed in the generated data can be based on either inputted PDB models or MRC files and manipulated with Chimera commands.
* Generated datasets are then available to be processed with any cryo-ET software; automatic processing options are available currently for the `EMAN2 <https://blake.bcm.edu/emanwiki/EMAN2>`_ , `IMOD <https://bio3d.colorado.edu/imod/>`_ (batchruntomo), and `I3 <i3link>`_ (sub-tomogram averaging only) pipelines.

=================
Table of Contents
=================

.. toctree::
    Installation
    Simulation
    Processing
    Guides
    Technical/Technical

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
