% Example script to set up for a SubTomogramAverageMPI run.
% Loads in motivelists containt picked particle locations, extracts them
% from the corresponding tomograms, and write the particles and the final 
% global motivelist out as *.em files. Also creates simple files for the
% mask, wedge, and ccmask.

%% Load motl:
% Change the filenames to the motivelist you want to use and adjust the
% tomonr according to your tomogram numbers and the amount of tomograms

% Use the get_motl_names_and_tomonrs.py script to write out the motls.txt 
% and tomonums.txt files shown in example below

% motl_filesnames = matrix of motl filenames
motl_filenames = readcell("/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/motls.txt", 'Delimiter', ' ');

% tomonr = matrix of tomogram numbers
tomonr = cell2mat(readcell("/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/tomonums.txt", 'Delimiter', ' '));

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

end;

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
        sprintf(convertStringsToChars(folder + "/" + base + "_SART_HR_1k.em"));
end



% Extract and write out the particles
particles_folder = '/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/parts';
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
artia.particle.extract_write(global_motl, 1, tomo_filenames, 64, 0, 0, ...
    1, particles_prefix);

%% Set up other inputs to averaging
% Mask: Set the directory where your mask should be saved and change the
% filename according to your parameters
% Below we create a spherical mask; the sphere function takes as input
% sphere(dims, radius, sigma, center)
maskFile = '/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/other/mask.em';
mask = artia.mask.sphere([128 128 128], 60, 3, [64 64 64]);
artia.em.write(mask, maskFile);

% Wedge: Set the directory where your mask should be saved and change the
% filename according to your parameters
% We create a basic, binary missing wedge file here.
wedgeFile = '/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/other/wedge.em';
wedge = artia.wedge.primitive([128 128 128], -54, 54);
artia.em.write(wedge, wedgeFile);

% CCMask: similar to mask, the cross-correlation mask is used to limit the 
% transformation of the particles while aligning
maskCCFile = '/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/other/maskCC_small.em';
maskCC = artia.mask.sphere([128 128 128], 28, 0, [64 96 64]);
artia.em.write(maskCC, maskCCFile);

% Motl file
motlFile = '/data/kshin/T4SS_sim/PDB/c4/IMOD/Artia/motls/motl_1.em';
artia.em.write(global_motl, motlFile);





