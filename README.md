# ETSimulations
Automated pipeline to generate and process simulated cryo-electron tomography data

## Getting started
The ETSimulations package is designed to be a tool to facilitate generation and processing of simulated cryo-electron tomography data. As of this preliminary version, only the generation of simulated tilt stacks is well-supported and covered by this manual.

### External dependencies
The following external software is used by ETSimulations and should thus be installed first:

* Chimera - https://www.cgl.ucsf.edu/chimera/

* TEM-simulator - http://tem-simulator.sourceforge.net/

* Python 3.3 or greater

### Setting up ETSimulations
To begin, navigate to a directory in which you want to install the package and run the following commands:

```
git clone https://github.com/kmshin1397/ETSimulations.git

cd ETSimulations

python3 -m venv env

source env/bin/activate

pip install -r requirements.txt
```

This will have downloaded the ETSimulations code and set up the necessary Python packages and environment.

### Running a simulation
Most all general parameter set up is done through a YAML file which is passed in as an argument to the main ets_run.py program. An example such YAML file is provided in the ETSimulations directory as "configs.yaml".

Detailed set-up with regards to the characteristics of the particles simulated are controlled through custom "Assembler" Python classes which can define a series of Chimera commands to open, manipulate, and combine one or more source maps, i.e. various proteins, into a fake particle source. (This is done for the T4SS simulations in the src/assemblers/t4ss_assembler.py file) Custom arguments to pass along to your custom particle Assemblers can also be defined in the configuration YAML file, as shown in the example.

To actually run a set of simulations, run (assuming you've activated the virtual environment as indicated above - the "source ..." command):

```
python src/ets_run.py -i configs.yaml
```

More details on the parameters available through the configurations can be found in the full user manual.
