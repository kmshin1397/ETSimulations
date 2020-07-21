% Example script to set up for a SubTomogramAverageMPI run.
% Loads in motivelists containt picked particle locations, extracts them
% from the corresponding tomograms, and write the particles and the final 
% global motivelist out as *.em files. Also creates simple files for the
% mask, wedge, and ccmask.

%% Input parameters
sta_folder = '/data/kshin/T4SS_sim/PDB/test_depths/processed_data/Artiatomi/sta';
info_file = '/data/kshin/T4SS_sim/PDB/test_depths/processed_data/Artiatomi/tomo_motls.txt'; 
maskFile = '/data/kshin/T4SS_sim/PDB/test_depths/processed_data/Artiatomi/sta/other/mask.em'; 
wedgeFile = '/data/kshin/T4SS_sim/PDB/test_depths/processed_data/Artiatomi/sta/other/wedge.em'; 
maskCCFile = '/data/kshin/T4SS_sim/PDB/test_depths/processed_data/Artiatomi/sta/other/maskCC.em'; 
motlFile = '/data/kshin/T4SS_sim/PDB/test_depths/processed_data/Artiatomi/sta/motls/motl_1.em'; 
motlFilePre = '/data/kshin/T4SS_sim/PDB/test_depths/processed_data/Artiatomi/sta/motls/motl_';
particles_folder = '/data/kshin/T4SS_sim/PDB/test_depths/processed_data/Artiatomi/sta/parts'; 
partFilePre = '/data/kshin/T4SS_sim/PDB/test_depths/processed_data/Artiatomi/sta/parts/part_';
box_size = 128; 
output_suffix = ''; 
avgCfgFile = '';
angIter = 10;
angIncr = 0.1;
phiAngIter = 10;
phiAngIncr = 0.1;
avgLowPass = 12;
avgHighPass = 0;
avgSigma = 3;

%% Load motl
% Change the filenames to the motivelist you want to use and adjust the
% tomonr according to your tomogram numbers and the amount of tomograms

% Use the get_motl_names_and_tomonrs.py script to write out the motls.txt 
% and tomonums.txt files shown in example below

tomo_info = readtable(info_file, 'Delimiter', ' ');


% motl_filesnames = matrix of motl filenames
motl_filenames = tomo_info.Motl;

% tomonr = matrix of tomogram numbers
tomonr = tomo_info.Tomonum;

%% Loop and write stuff into motls
% Set up a global motivelist of all particles
global_motl = [];

for i = 1:numel(tomonr)
    % Read motl
    motl = artia.em.read(motl_filenames{i});
    
    % Tomogram number .
    motl(5,:) = tomonr(i);

    % Particle number
    motl(6,:) = 1:size(motl, 2);

    % Clean motl
    motl(1,:) = 0 ;
    motl(20,:) = 0 ;
    
    % Save motl
    artia.em.write(motl , motl_filenames{i});

    % Append to global motivelist 
    global_motl = [global_motl motl];

end

%% Extract particles

% Low contrast, high resolution tomograms should be used for averaging.
% Set up an array of tomogram filenames, where the tomogram number is the 
% filename's index within the array
tomo_filenames = strings([1, max(tomonr)]);
for i = 1 : numel(tomonr)
    tomo_no = tomonr(i);
    motl_file = convertCharsToStrings(motl_filenames{i});
    [folder, name, ext] = fileparts(motl_file);
    split_base = strsplit(name, "_motl");
    base = split_base(1);
    % Add 1 for 0 indexed for my sims
    tomo_filenames{tomo_no} = ...
        sprintf('%s/%s%s',folder, base, output_suffix);
end



% Extract and write out the particles
particles_prefix = sprintf('%s/part_', particles_folder);

% See documentation for artia.particle.extract_write for more details on 
% what these arguments represent and the values they can take
% Params used here:
% motivelistFilename = global_motl
% upScaleFactor = 1
% tomogramFilenameArray = tomo_filenames
% r = 64
% doRotation = 0
% doTranslate = 0
% doNormalize = 1
% partPref = particles_prefix
artia.particle.extract_write(global_motl, 1, tomo_filenames, box_size/2, 0, 0, ...
    1, particles_prefix);

%% Set up other inputs to averaging
% Mask: Set the directory where your mask should be saved and change the
% filename according to your parameters
% Below we create a spherical mask; the sphere function takes as input
% sphere(dims, radius, sigma, center)
mask = artia.mask.sphere([box_size box_size box_size], box_size/2, 3, [box_size/2 box_size/2 box_size/2]);
artia.em.write(mask, maskFile);

% Wedge: Set the directory where your mask should be saved and change the
% filename according to your parameters
% We create a basic, binary missing wedge file here.
wedge = artia.wedge.primitive([box_size box_size box_size], -54, 54);
artia.em.write(wedge, wedgeFile);

% CCMask: similar to mask, the cross-correlation mask is used to limit the 
% transformation of the particles while aligning
maskCC = artia.mask.sphere([box_size box_size box_size], box_size/4, 0, [box_size/2 box_size/2 box_size/2]);
artia.em.write(maskCC, maskCCFile);

% Motl file
artia.em.write(global_motl, motlFile);

% Averaging parameters
avg = struct();
avg.CudaDeviceID = '0 1 2 3';
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
avg.Reference = sprintf('%s/ref/ref', sta_folder);
avg.Mask = maskFile;
avg.MaskCC = maskCCFile;
avg.NamingConvention = 'TomoParticle';
avg.StartIteration = '1';
avg.EndIteration = '2';
avg.AngIter = num2str(angIter);
avg.AngIncr = num2str(angIncr);
avg.PhiAngIter = num2str(phiAngIter);
avg.PhiAngIncr = num2str(phiAngIncr);
avg.LowPass = num2str(avgLowPass);
avg.HighPass = num2str(avgHighPass);
avg.Sigma = num2str(avgSigma);
artia.cfg.write(avg, avgCfgFile);
