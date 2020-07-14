% Example script to set up for a set of Artiatomi reconstructions with
% EmSART based on IMOD alignments produced previously. Also includes
% setting up Artiatomi motivelists if particles have already been picked
% You may need to edit parts of this script/comment out unnecessary parts
% based on what parts you need and on your project directory
% structure/input file formats
%
% For each stack/subdirectory in the IMOD project root:
% 1) Converts IMOD alignment to Artiatomi marker alignment files
% 2) Write out an EmSART reconstruction configuration file based on a
% template file provided
% 3) Build up an Artiatomi motl based on particle locations passed in via a
% text/csv file and also load orientations for them based on PEET MOTL.
%

%% Input parameters
project_root = '';
dir_starts_with = '';
template_config = '';
output_suffix = '';
base_motl = '';
peet_motl = '';
tomogram_size_x = '';
tomogram_size_y = '';

%% Process
cd(project_root)
files = dir;
directoryNames = {files([files.isdir]).name};
for i = 3 : length(directoryNames)
    directory = directoryNames(i);
    if startsWith(directory{1}, dir_starts_with)
        cd(project_root + "/" + directory{1})
        % Get basename by finding the IMOD tlt file
        tlt_file_struct = dir('*.tlt');
        
        % We may get the fid tlt file back instead
        tlt_filename = erase(tlt_file_struct(1).name, "_fid");
        
        tlt_file = tlt_file_struct(1).folder + "/" + tlt_filename;
        [filepath, basename, ext] = fileparts(tlt_file);
        current_full_path = tlt_file_struct(1).folder;
        imod_root = current_full_path + "/" + basename;
        marker_output = current_full_path + "/" + basename + '_markers.em';

        %% Set up marker file
        % Convert IMOD alignment to Artia marker alignment
        ali = artia.geo.imod2emsart(char(imod_root));
        
        % Set up default marker header
        [xdim, ydim, zdim] = size(ali);
        marker_struct = struct();
        % The imod2emsart function converts the alignments per tilt, but 
        % does not retain specific marker locations. Thus, we just pass in
        % a fake, single marker position at (0,0,0)
        marker_struct.model = [0.0, 0.0, 0.0];
        marker_struct.ali = ali;
        marker_struct.dimX = xdim;
        marker_struct.dimY = ydim;
        marker_struct.dimZ = zdim;
        marker_struct.aliScore = 0;
        marker_struct.beamDeclination = 0;
        marker_struct.magAnisoFactor = 0;
        marker_struct.magAnisoAngle = 0;
        marker_struct.imageSizeX = tomogram_size_x;
        marker_struct.imageSizeY = tomogram_size_y;

        % Write out new marker file
        artia.marker.write(marker_struct, char(marker_output));
        
        % Set up config file
        % Copy over base config file
        [filepath, config_basename, ext] = fileparts(template_config);
        config_out = current_full_path + "/" + config_basename + ext;
        copyfile(template_config, config_out);

        % Edit input/output file params
        input_stack = current_full_path + "/" + basename + ".st";
        output_volume = current_full_path + "/" + basename + output_suffix;
        artia.cfg.modify({config_out}, {config_out}, ...
            "ProjectionFile", {input_stack}, ...
            "OutVolumeFile", {output_volume}, ...
            "MarkerFile", {marker_output});
        
        % Convert MOTLs to EmSART format
        % Tomo num is extracted from subdirectory names
        split_base = split(directory{1}, "_");
        % Add one to tomonumber in filename to account for Matlab being
        % 1-indexed
        tomo_num = str2double(split_base(end)) + 1;
        new_motl = artia.motl.tbl2motl(base_motl, tomo_num, 0);
        
        % Add pre-orientations
        peet_motl_table = readtable(peet_motl);
        peet_motl = table2array(peet_motl_table);
        for i = 1:size(peet_motl, 1)
            new_motl(17:19, i) = peet_motl(i,17:19);
        end        
        
        motl_out = current_full_path + "/" + basename + "_motl.em";
        artia.em.write(new_motl, motl_out);
    end
end