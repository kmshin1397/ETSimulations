import os


def eman2_main(general_args, eman2_args):
    """
    TODO

    1. Make EMAN2 dir
    2. Copy over template scripts
    3. If run automatically, run scripts up to end point

    Returns:

    """

    # Set up an EMAN2 directory
    processed_data_dir = general_args["root"] + "/processed_data"
    e2_dir = processed_data_dir + "/EMAN2"
    if not os.path.exists(e2_dir):
        os.mkdir(e2_dir)





    pass
