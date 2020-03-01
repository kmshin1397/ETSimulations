import pytest
import src.simulation.tem_simulation as simulation


@pytest.fixture(scope="session")
def base_test_config():
    return "=== simulation ===\n" + \
           "log_file = old_log_file.txt\n"+ \
           "=== detector ===\n" + \
           "image_file_out = old_test_tiltseries.mrc\n" + \
           "=== detector ===\n" + \
           "image_file_out = old_test_tiltseries_nonoise.mrc\n"


@pytest.fixture(scope="session")
def test_simulation(tmpdir_factory, base_test_config):
    # Set up an initial test configuration file
    subdir = tmpdir_factory.mktemp("subdir")
    test_config_file = subdir.join("test.txt")
    test_config_file.write(base_test_config)

    sim = simulation.Simulation(str(test_config_file), "", "new_test_tiltseries.mrc",
                                "new_test_tiltseries_nonoise.mrc", 0, str(subdir))

    return sim


def test_edit_output_files(test_simulation):
    test_simulation.edit_output_files()
    with open(test_simulation.config_file, 'r') as f:
        # Read simulation segment
        f.readline()
        assert f.readline() == "log_file = %s/simulator.log\n" % test_simulation.temp_dir

        # Read first detector segment (the noisy one)
        f.readline()
        assert f.readline() == "image_file_out = new_test_tiltseries.mrc\n"

        # Read second detector segment (the no-noise one)
        f.readline()
        assert f.readline() == "image_file_out = new_test_tiltseries_nonoise.mrc\n"


def test_run_tem_simulator(test_simulation, mocker):
    def mock_check_output(commands):
        assert commands == [tem_exec_path, test_simulation.config_file]

    mocker.patch.object(simulation, "check_output", mock_check_output)
    tem_exec_path = "test_path"
    test_simulation.run_tem_simulator(tem_exec_path)


def test_create_particle_lists(test_simulation, base_test_config, mocker):
    mock_particle_set = mocker.Mock()
    mock_particle_set.name = "test_name"
    mock_particle_set.orientations = [[0, 0, 0], [90, 90, 90]]
    mock_particle_set.coordinates = [[0, 0, 0], [100, 100, 100]]
    mock_particle_set.source = "test_model_source.mrc"
    mock_particle_set.num_particles = 2

    initial_config_file = open(test_simulation.config_file, 'r').read()

    test_simulation.create_particle_lists([mock_particle_set])

    new_coord_file = "%s/test_name_coord.txt" % test_simulation.temp_dir

    with open(test_simulation.config_file, 'r') as f:
        new_particle_segment = \
            "=== particle test_name ===\n" + \
            "source = map\n" + \
            "map_file_re_in = %s\n" % mock_particle_set.source + \
            "use_imag_pot = no\n" + \
            "famp = 0\n\n"
        new_particle_set_segment = \
            "=== particleset ===\n" + \
            "particle_type = test_name\n" + \
            "num_particles = %d\n" % 2 + \
            "particle_coords = file\n" + \
            "coord_file_in = %s\n\n" % new_coord_file
        expected_new_file = initial_config_file + new_particle_segment + new_particle_set_segment

        assert f.read() == expected_new_file

    with open(new_coord_file, 'r') as f:
        # The first row of the coordinates file states the number of particles, and that each row
        # has 6 values (3 for the position and 3 for the orientation angles)
        row = f.readline().split()
        assert [int(row[0]), int(row[1])] == [mock_particle_set.num_particles, 6]

        for i in range(mock_particle_set.num_particles):
            row = f.readline().split()
            coordinate = [int(row[0]), int(row[1]), int(row[2])]
            orientation = [int(row[3]), int(row[4]), int(row[5])]
            assert coordinate == mock_particle_set.coordinates[i]
            assert orientation == mock_particle_set.orientations[i]






