========================
Installation
========================

---------------------
External dependencies
---------------------
The following external software is used by ETSimulations and should thus be installed first:

* Chimera - https://www.cgl.ucsf.edu/chimera/ (Only needed if you wish to simulate data sets)

* TEM-simulator - http://tem-simulator.sourceforge.net/ (Only needed if you wish to simulate data sets)

* Python 3.3 or greater

* Corresponding softwares for the various Processors (i.e. EMAN2 for the EMAN2 Processor) that you wish to run

------------------------
Setting up ETSimulations
------------------------
To begin, navigate to a directory in which you want to install the package and run the following commands::

    git clone https://github.com/kmshin1397/ETSimulations.git

    cd ETSimulations

    python3 -m venv env

    source env/bin/activate

    pip install -r requirements.txt


This will have downloaded the ETSimulations code and set up the necessary Python packages and environment.
