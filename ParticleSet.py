class ParticleSet:
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
        self.coordinates.append(coord)

    def add_orientation(self, orientation):
        self.orientations.append(orientation)

    def add_source(self, source):
        self.source = source

