import pytest
import yaml
import ets_generate_data as ets
import io
from shutil import rmtree


@pytest.fixture(scope="module")
def test_configs():
    # Load in the example configs included in the repo to be used for testing the data generation
    example_configs = """---\n
    # Persistent configs\n
    tem_simulator_executable: "/home/kshin/Documents/software/TEM-simulator_1.3/src/TEM-simulator"\n
    chimera_exec_path: "/usr/sbin/chimera"\n
    \n
    # Run-specific configs\n
    model: "/data/kshin/T4SS_sim/PDB/pdb_maps/barrel_chimera.mrc"\n
    root: "/data/kshin/T4SS_sim/PDB/test"\n
    config: "/data/kshin/T4SS_sim/PDB/test/template_files/sim.txt"\n
    coord: "/data/kshin/T4SS_sim/PDB/test/template_files/T4SS_coord.txt"\n
    num_stacks: 2\n
    name: "T4SS"\n
    num_cores: 2\n
    # apix in nm\n
    apix: 0.283\n
    num_chimera_windows: 1\n
    defocus_values: [1, 5, 10]\n
    bead_map: "/data/kshin/T4SS_sim/bead.mrc"\n
    \n
    # Custom configs\n
    custom_configs:\n
      membrane_path: "/data/kshin/T4SS_sim/PDB/pdb_maps/mem_chimera.mrc"\n
      orientations_tbl: "/data/kshin/T4SS_sim/manual_full.tbl"\n
      rod: "/data/kshin/T4SS_sim/PDB/pdb_maps/rod_chimera.mrc"\n
      barrel: "/data/kshin/T4SS_sim/PDB/pdb_maps/barrel_chimera.mrc"\n
    """
    stream = io.StringIO(example_configs)
    return yaml.load(stream, Loader=yaml.FullLoader)


@pytest.fixture(scope="module")
def base_test_config():
    return "=== simulation ===\n" + \
           "log_file = old_log_file.txt\n"+ \
           "=== detector ===\n" + \
           "image_file_out = old_test_tiltseries.mrc\n" + \
           "=== detector ===\n" + \
           "image_file_out = old_test_tiltseries_nonoise.mrc\n" + \
           "=== optics ===\n" + \
           "defocus_nominal = 0\n"


@pytest.fixture(scope="module")
def base_test_coords():
    return "# Random comment\n2 6\n0 0 0 0 0 0\n100 100 100 0 0 0\n"


def test_project(tmpdir_factory, test_configs, mocker, base_test_config, base_test_coords):
    # Set up an initial test project directory
    root = tmpdir_factory.mktemp("root")
    test_tem_configs = root.join("sim.txt")
    test_tem_coords = root.join("coords.txt")
    test_tem_configs.write(base_test_config)
    test_tem_coords.write(base_test_coords)
    test_configs["root"] = str(root)
    test_configs["config"] = str(test_tem_configs)
    test_configs["coord"] = str(test_tem_coords)

    # TODO: Implement if T4SS vs default
    mock_orientations = "0 0 0 0 0 0 0 0 0 0\n0 0 0 0 0 0 0 0 0 0\n"
    test_orientations = root.join("orientations.tbl")
    test_orientations.write(mock_orientations)
    test_configs["custom_configs"]["orientations_tbl"] = str(test_orientations)

    # Mock out HTTP requests
    mock_requests = mocker.Mock()
    mock_requests.get = lambda request, params: None
    mocker.patch.object(ets, "requests", mock_requests)

    # Mock out Chimera server
    def mock_chimera_init(exec_path):
        mock_chimera_server = mocker.Mock()
        mock_chimera_server.start_chimera_server = lambda: print("hi")
        mock_chimera_server.quit = lambda: None
        mock_chimera_server.get_port = lambda: 123
        mock_chimera_server.exec_path = exec_path
        return mock_chimera_server

    mocker.patch.object(ets, "ChimeraServer", mock_chimera_init)

    # Mock out logging
    mock_logger = mocker.Mock()
    mock_logger.info = lambda msg: print(msg)
    mock_logger.debug = lambda msg: print(msg)
    mocker.patch.object(ets, "logger", mock_logger)

    # Mock out Simulation run
    # TODO mock out all of Simulation so we can track calls
    mocker.patch.object(ets.Simulation, "run_tem_simulator")
    ets.Simulation.run_tem_simulator.return_value = None

    # Mock out Assembler
    mocker.patch.object(ets.T4SSAssembler, "set_up_tiltseries", lambda a, b: b)

    # Mock out scale function for this main function test
    mocker.patch.object(ets, "scale_mrc", lambda a, b: None)

    ets.main(test_configs)
    ets.Simulation.run_tem_simulator.assert_called()

