% Example script to run the EmSARTSubVols program for each tomogram in the
% data set to extract the particles based on local refinement values so
% that they can be averaged again.

%% Input parameters
emsart_subvols_path = '/home/kshin/Documents/repositories/Artiatomi/build/EmSARTSubVols';
refineDir = '/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/refine';
subVolPre = '/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/refine/subvols/';
latestStaMotl = '/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/motls/motl_2.em';
maskFile = '/data/kshin/T4SS_sim/PDB/test_depths2/processed_data/Artiatomi/sta/other/mask.em'; 
wedgeFile = '/data/kshin/T4SS_sim/PDB/test_depths2/processed_data/Artiatomi/sta/other/wedge.em'; 
maskCCFile = '/data/kshin/T4SS_sim/PDB/test_depths2/processed_data/Artiatomi/sta/other/maskCC.em'; 
angIter = 3; 
angIncr = 2; 
phiAngIter = 3; 
phiAngIncr = 2; 
avgLowPass = 12; 
avgHighPass = 0; 
avgSigma = 3; 

%% Run extractions
motlFilePre = sprintf('%s/average/motls/motl_', refineDir); 
partFilePre = sprintf('%s/part_', subVolPre); 
subVolCfgs = sprintf('%scfgs', subVolPre);
mkdir(subVolPre);
mkdir(subVolCfgs);
cd(refineDir)
files = dir;
directoryNames = {files([files.isdir]).name};

for i = 3 : length(directoryNames)
    directory = directoryNames(i);
    % For each tomogram
    if startsWith(directory{1}, "tomo")
        list_files = dir(sprintf('%s/iter*', directory{1}));
        % Get the path to the last iteration of EmSARTRefine refinement
        last_iter = 0;
        last_iter_dir = '';
        for j = 1 : length(list_files)
            iter = list_files(j).name(end); 
            iter_num = str2num(iter);
            if iter_num > last_iter
                last_iter = iter_num;
                last_iter_name = list_files(j).name;
                last_iter_dir = sprintf('%s/%s/%s', refineDir, ...
                    directory{1}, last_iter_name);
            end
        end
        % Retrieve the EmSART configs
        list_files = dir(sprintf('%s/*refine*.cfg',last_iter_dir));
        refine_cfg = artia.cfg.read(sprintf('%s/%s', last_iter_dir, list_files(1).name));
        
        subVolCfgFile = sprintf('%s/%s_subvol.cfg', subVolCfgs, directory{1});
        config = refine_cfg;
        config.ShiftInputFile = config.ShiftOutputFile;
        config = rmfield(config, 'ShiftOutputFile');
        config.BatchSize = num2str(size(artia.em.read(config.MotiveList), 2));
        config.SubVolPath = subVolPre;
        config.NamingConvention = 'TomoParticle';
        artia.cfg.write(config, subVolCfgFile);
        
        artia.mpi.run(emsart_subvols_path, 1, subVolCfgFile, 'runRemote', true, 'remoteHost', 'Artiatomi@localhost', 'remotePort','portnumber','suppressOutput', false);
    end
end
m = artia.em.read(latestStaMotl);
m(11:13, :) = 0;
mkdir(sprintf('%s/average', refineDir));
mkdir(sprintf('%s/average/motls', refineDir));
artia.em.write(m, sprintf('%s/average/motls/motl_1.em', refineDir));

