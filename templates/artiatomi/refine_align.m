% Example script to set up for iterative local refinement on a set of 
% tomograms. With the artiatomi-tools Docker image, the executables should
% all be on the PATH variable and the locations shouldn't need to be more
% than just the executable name for it to work (instead of the full paths
% seen below).

%% Input parameters
main_root = '';
latest_motl = '';
info_file = '';
refine_motls_dir = '';
latest_ref = '';
mask_file = '';
wedge_file = '';
maskCC_file = '';
tomogram_size_x = '';
tomogram_size_y = '';
tomogram_size_z = '';
box_size = 64;


%% Split latest motivelist into motivelists for each tomogram
motl = artia.em.read(latest_motl);
tomo_info = readtable(info_file, 'Delimiter', ' ');
tomonr = tomo_info.Tomonum;
data_dirs = tomo_info.Directory;

for i = 1:numel(tomonr)
    idx = motl(5,:)==tomonr(i);
    tomo_motl = motl(:,idx);
    
    % Write out the individual motivelists
    artia.em.write(tomo_motl, ...
        sprintf('%s/%d_ref_motl.em', refine_motls_dir, tomonr(i)));
end

%% Create a refinement reference by overlaying the mask and the latest ref
% Load mask and latest reference
ref = artia.em.read(latest_ref);
mask = artia.em.read(mask_file);
% Overlay them
ref_mask = (ref .* mask);
avg_ref_mask = mean(ref_mask(:));
std_ref_mask = std(ref_mask(:));

ref_refinement = (ref_mask - avg_ref_mask) ./ std_ref_mask;
artia.em.write(ref_refinement, sprintf('%s/ref_refinement.em', main_root));

%% Set up general options 
opts = struct();

% General options
opts.iters = 3; % Iters per tomogram
opts.nodes = 1;

% Executable locations and remote setup
opts.cAligner = '/home/kshin/Documents/repositories/cAligner/build/cAligner';
opts.EmSART = '/home/kshin/Documents/repositories/Artiatomi/build/EmSART';
opts.EmSARTRefine = '/home/kshin/Documents/repositories/Artiatomi/build/EmSARTRefine';
opts.STA = 'SubTomogramAverageMPI';
opts.STA_dir = '/home/kshin/Documents/repositories/Artiatomi/build';
opts.remote = true;
opts.host = 'Artiatomi@localhost';
% This should be the port number given by start_artia.sh when the Docker
% container is started
opts.port = 'port number';

% Reconstruction parameters
opts.reconDim = [tomogram_size_x tomogram_size_y tomogram_size_z];
opts.imDim = [2000 2000]; % 2k image stack
opts.volumeShifts = [0 0 0];
opts.maAmount = 1;
opts.maAngle = 0;
opts.voxelSize = 2;

% Averaging parameters
opts.boxSize = box_size;
opts.wedge = artia.em.read(wedge_file);
opts.mask = artia.em.read(mask_file);
opts.reference = artia.em.read(sprintf('%s/ref_refinement.em', main_root));
opts.maskCC = artia.em.read(maskCC_file);
opts.angIter = 10;
opts.angIncr = 0.1;
opts.phiAngIter = 10;
opts.phiAngIncr = 0.1;
opts.avgLowPass = 12;
opts.avgHighPass = 0;
opts.avgSigma = 3;

% Refinement (projection matching) parameters
opts.groupMode = 'MaxDistance';
opts.maxDistance = 150;
opts.groupSize = 20;
opts.maxShift = 15;
opts.speedUpDist = 60;

% Refinement band pass filter
opts.lowPass = 200;
opts.lowPassSigma = 50;
opts.highPass = 20;
opts.highPassSigma = 10;

% Volume size computation
opts.borderSize = 5*opts.boxSize;

%% Set tomogram-specific options and run
% For some reason this may randomly freeze/not work for some tomograms so
% it is probably a good idea to periodically check in and restart this
% section from a later index i (by changing that 1 in 1:numel(tomonr)) to
% skip problematic tomograms.
for i = 1:numel(tomonr)
    
    tomoNum = tomonr(i);
    data_dir = data_dirs(i);
    [~, basename, ~] = fileparts(data_dir);
    % minus 1 for the tomogram number because we 1-indexed the tomonr array
    opts.projFile = sprintf('%s/%s.st', data_dir, basename);
    opts.markerFile = sprintf('%s/%s_markers.em', data_dir, basename);
    opts.projDir = sprintf('%s/tomo_%d', main_root, tomoNum);
    opts.tomoNr = tomoNum;
    opts.motl = artia.em.read(sprintf('%s/motls/%d_ref_motl.em', main_root, tomoNum));
    
    % RUN!
    refineAlign.iterative_alignment(opts)
    
end
