class ParticleSet:
    """ Represents a set of particles of the same kind within a TEM-Simulator run.

    This class directly corresponds to the particleset segments defined within a configuration file
    for the TEM-Simulator software.

    Attributes:
        name: The name of the particle (within the TEM-Simulator configurations) which this
            particle set consists of
        source: The source MRC or PDB file of the particle associated with the particle set
        coordinates: A list of XYZ coordinates within the sample volume at which the particles in
            the set should be located
        orientations: A list of ZXZ Euler angles (external) to rotate the particles in the set.
        num_particles: The number of particles in the set
        key: Flag to indicate that this is part of the particles of interest (the ones that will be
            averaged), versus say just fake gold fiducials added to facilitate processing

    Methods:
        add_coordinate(coord): Append an XYZ coordinate to the list of particle coordinates
        add_orientation(orientation): Append an ZXZ Euler angle rotation to the list of particle
            orientations
        add_source(source): Set the particle source file for the particle set

    """
    def __init__(self, name, key=False):
        self.name = name
        self.source = None
        self.coordinates = []
        self.orientations_to_simulate = []
        self.orientations_to_save = []
        self.noisy_orientations = []
        self.num_particles = 0

        # Flag to indicate that this is part of the particles of interest (the one that will be
        # averaged)
        self.key = key

    def add_coordinate(self, coord):
        """ Append an XYZ coordinate to the list of particle coordinates """
        self.coordinates.append(coord)

    def add_orientation_to_simulate(self, orientation, noisy_version=None):
        """
        Append a ZXZ orientation to the list of particle orientations to simulate.

        Args:
            orientation: The true orientation to pass along to the TEM-Simulator
            noisy_version: A noisy version of the orientation to record for processing purposes

        Returns: None

        """
        self.orientations_to_simulate.append(orientation)
        if noisy_version:
            self.noisy_orientations.append(noisy_version)

    def add_orientation_to_save(self, orientation):
        """
        Append a ZXZ orientation to the list of particle orientations to record. This can be used to save orientations
            other than the ones sent to TEM-Simulator in the metadata

        Args:
            orientation: The orientation to save in the metadata

        Returns: None

        """
        self.orientations_to_save.append(orientation)

    def add_source(self, source):
        """ Set the particle source file for the particle set """
        self.source = source

