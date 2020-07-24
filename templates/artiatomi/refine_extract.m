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
lowPass = 12;
highPass = 0;
sigma = 3;

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
mkdir(sprintf('%s/average/ref', refineDir));
artia.em.write(m, sprintf('%s/average/motls/motl_1.em', refineDir));

avgCfgFile = sprintf('%s/average/sta.cfg', refineDir)

% Averaging parameters
avg = struct();
avg.CudaDeviceID = '0';
avg.WedgeIndices = '';
avg.Classes = '';
avg.MultiReference = 'false';
avg.PathWin = '';
avg.PathLinux = '';
avg.NamingConvention = 'TomoParticle';
avg.ClearAngles = 'false';
avg.BestParticleRatio = '1';
avg.ApplySymmetry = 'transform';
avg.CouplePhiToPsi = 'true';
avg.MotiveList = motlFilePre;
avg.WedgeFile = wedgeFile;
avg.Particles = partFilePre;
avg.Reference = sprintf('%s/average/ref/ref', refineDir);
avg.Mask = maskFile;
avg.MaskCC = maskCCFile;
avg.NamingConvention = 'TomoParticle';
avg.StartIteration = '1';
avg.EndIteration = '2';
avg.AngIter = num2str(angIter);
avg.AngIncr = num2str(angIncr);
avg.PhiAngIter = num2str(phiAngIter);
avg.PhiAngIncr = num2str(phiAngIncr);
avg.LowPass = num2str(lowPass);
avg.HighPass = num2str(highPass);
avg.Sigma = num2str(sigma);
artia.cfg.write(avg, avgCfgFile);
