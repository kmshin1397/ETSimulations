Simulating the T4SS
===================
Included in the ETSimulations repository are example files relating to the simulation of Type IV Secretion Systems. This tutorial covers the process of generating a data set from these as a way to demonstrate the simulation workflow. 
Rest of tutorial to be completed.

.. _tutorial-t4ss-assembler:

==================
The T4SS Assembler
==================

The T4SS Assembler class implements an Assembler to generate and modify fake particles using Chimera designed to approximate the structure of the Type IV Secretion System. It will create particles consisting of an inner

--------------
Custom configs
--------------
The parameters available for the T4SS Assembler through the YAML custom\_configs are:

    * **membrane\_path** : string
        The file path to the membrane segment MRC representing the inner membrane
    * **orientations\_tbl** : string
        A Dynamo orientations table which contains particle orientations found from a real data set, used to approximate the real-life particle orientation distribution

    * **rod** : string
        The path to the MRC to use for the rods

    * **root** : string
        The path to the MRC to use for the central barrel

    * **num_rods** : integer
        The number of rods to place symmetrically around the central barrel

    * **rod_distance_from_center** : float
        The distance away from the center of the barrel to place rods, i.e. the radius

---------------
Metadata output
---------------
Each stack simulated with the T4SS pipeline will produce the following metadata object within the **sim\_metadata.json** file outputted.