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
        add_coordinate: Append an XYZ coordinate to the list of particle coordinates
        add_orientation: Append an ZXZ Euler angle rotation to the list of particle orientations
        add_source: Set the particle source file for the particle set

    """
    def __init__(self, name, key=False):
        self.name = name
        self.source = None
        self.coordinates = []
        self.orientations = []
        self.num_particles = 0

        # Flag to indicate that this is part of the particles of interest (the one that will be
        # averaged)
        self.key = key

    def add_coordinate(self, coord):
        """ Append an XYZ coordinate to the list of particle coordinates """
        self.coordinates.append(coord)

    def add_orientation(self, orientation):
        """ Append an ZXZ Euler angle rotation to the list of particle orientations """
        self.orientations.append(orientation)

    def add_source(self, source):
        """ Set the particle source file for the particle set """
        self.source = source

