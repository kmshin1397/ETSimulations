{
  name: "artiatomi",
  args: {
    real_data_mode: false,
    setup_reconstructions_and_motls: true,
    reconstruction_template_config: "/home/kshin/Documents/repositories/ETSimulations/templates/artiatomi/EmSART_HR.cfg",
    output_suffix: "_SART_HR_1k.em",
    tomogram_size_x: 1000,
    tomogram_size_y: 1000,
    tomogram_size_z: 300,
    position_binning: 2
  }
}


real:
{
  name: "artiatomi",
  args: {
    real_data_mode: true,
    setup_reconstructions_and_motls: true,
    reconstruction_template_config: "/home/kshin/Documents/repositories/ETSimulations/templates/artiatomi/EmSART_HR.cfg",
    output_suffix: "_SART_HR_1k.em",
    tomogram_size_x: 1000,
    tomogram_size_y: 1000,
    imod_dir: "/data/kshin/batchtomotest_nonraptor2",
    artia_dir: "/data/kshin/batchtomotest_nonraptor2/Artia",
    dir_starts_with: "dg",
    mod_contains: "T4SS_YL_2k"
  }
}

Make note that tomo nums are based off _ splitting