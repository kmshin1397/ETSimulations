%% dynamo_process.m

% The dynamo_process.m script attempts to automate the process of setting 
% up a Dynamo sub-tomogram averaging project starting from a .doc and .tbl
% file. 

% Kyung Min Shin, Caltech, 2020

%% Input parameters
basename = '';
doc_file = '';
tbl_file = '';
particles_dir = '';
box_size = 72;
num_workers = 12;
num_cores = 1;
project_name = '';
mask_path = '';
ite_r1 = '';
cr_r1 = '';
cs_r1 = '';
ir_r1 = '';
is_r1 = '';
rff_r1 = '';
rf_r1 = '';
dim_r1 = '';
lim_r1 = '';
limm_r1 = '';
nref_r1 = '';
high_r1 = '';
low_r1 = '';
sym_r1 = '';
dst = '';
gpus = '';

%% Process table
% Crop out the particles
dtcrop(doc_file, tbl_file, particles_dir, box_size, 'mw', num_workers);

% Randomize the azimuth
azrand=dynamo_table_randomize_azimuth(tbl_file);
azrand_file = sprintf('%s_azrand.tbl', basename);
dwrite(azrand, azrand_file);

% Split the table into even/odd particles
dynamo_table_eo(azrand_file, 'disk', 1);

even_tbl_file = sprintf('%s_azrand_even.tbl', basename);
az_e = daverage(particles_dir, 't', even_tbl_file, 'fcompensate', 1, ...
    'mw', num_workers);
dwrite(az_e.average,'averages/init_avg_azrand_even.em');

odd_tbl_file = sprintf('%s_azrand_odd.tbl', basename);
az_o = daverage(particles_dir, 't', odd_tbl_file, 'fcompensate', 1, ...
    'mw', num_workers);
avg_odd = 'averages/init_avg_azrand_odd.em';
dwrite(az_o.average,avg_odd);

%% Create project
dcp.new(project_name, 'd', particles_dir, 'template', avg_odd,'masks', ...
    'default', 't', odd_tbl_file);

% Project settings
dvput(project_name, 'd', 'mask', mask_path);
dvput(project_name, 'd', 'cores', num_cores);
dvput(project_name, 'd', 'mwa', num_workers);
dvput(project_name, 'd', 'ite_r1', ite_r1);
dvput(project_name, 'd', 'cr_r1', cr_r1);
dvput(project_name, 'd', 'cs_r1', cs_r1);
dvput(project_name, 'd', 'ir_r1', ir_r1);
dvput(project_name, 'd', 'is_r1', is_r1);
dvput(project_name, 'd', 'rff_r1', rff_r1);
dvput(project_name, 'd', 'rf_r1', rf_r1);
dvput(project_name, 'd', 'dim_r1', dim_r1);
dvput(project_name, 'd', 'lim_r1', lim_r1);
dvput(project_name, 'd', 'limm_r1', limm_r1);
dvput(project_name, 'd', 'nref_r1', nref_r1);
dvput(project_name, 'd', 'high_r1', high_r1);
dvput(project_name, 'd', 'low_r1', low_r1);
dvput(project_name, 'd', 'sym_r1', sym_r1);
dvput(project_name, 'd', 'dst', dst);
dvput(project_name, 'd', 'gpus', gpus);

dvcheck(project_name);
dvunfold(project_name);
