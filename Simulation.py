import json


class Simulation:

    def __init__(self, coordinates_file, sim_input_file,
                 metadata_file, particle_map_file, tiltseries_file,
                 nonoise_tilts_file, keep_temps=False, particles_per_stack=4):
        self.coordinates_file = coordinates_file
        self.sim_input_file = sim_input_file
        self.metadata_file = metadata_file
        self.particle_map_file = particle_map_file
        self.tiltseries_file = tiltseries_file
        self.nonoise_tilts_file = nonoise_tilts_file
        self.orientations = []
        self.angles = []
        self.keep_temps = keep_temps
        self.particles_per_stack = particles_per_stack

    def add_angle(self, angle):
        self.angles.append(angle)

    def extend_angles(self, angles):
        self.angles.extend(angles)

    def add_orientation(self, orientation):
        self.orientations.append(orientation)

    def extend_orientations(self, orientations):
        self.orientations.extend(orientations)

    def set_keep_temps(self, keep_temps):
        self.keep_temps = keep_temps

    def to_json(self):
        return json.dumps(self.__dict__, indent=4)

    def print_contents(self):
        print("Simulation:")
        print(".   coordinates_file: %s" % self.coordinates_file)
        print(".   sim_input_file: %s" % self.sim_input_file)
        print(".   particle_map_file: %s" % self.particle_map_file)
        print(".   tiltseries_file: %s" % self.tiltseries_file)
        print(".   nonoise_tilts_file: %s" % self.nonoise_tilts_file)
        print(".   angle: %.2f" % self.angle)
        print(".   orientation: %d, %d, %d" % self.orientation)

    def stringify(self):
        lines = ["Simulation",
                 ".   coordinates_file: %s" % self.coordinates_file,
                 ".   sim_input_file: %s" % self.sim_input_file,
                 ".   particle_map_file: %s" % self.particle_map_file,
                 ".   tiltseries_file: %s" % self.tiltseries_file,
                 ".   nonoise_tilts_file: %s" % self.nonoise_tilts_file,
                 ".   angle: %.2f" % self.angle,
                 ".   orientation: %d, %d, %d" % self.orientation]
        return "\n".join(lines)
