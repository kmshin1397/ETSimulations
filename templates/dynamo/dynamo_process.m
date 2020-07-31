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
project_name = '';
mask = '';
cores = 1;
mwa = '';
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
invert_particles = 1;

%% Process table
% Crop out the particles
dtcrop(doc_file, tbl_file, particles_dir, box_size, 'mw', num_workers);

if invert_particles
    new_table=dread([particles_dir, '/crop.tbl']);
    parfor i=1:size(new_table,1)
        particle_name = [particles_dir,'/particle_',sprintf('%06d',i),'.em'];
        particle = dread(particle_name);
        inverted_particle=dparticle(particle,'inv',1);
        dwrite(inverted_particle,[particles_dir,'/particle_',sprintf('%06d',i),'.em']);
    end
end

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

%% Create odd project
project_name_odd = sprintf('%s_odd', project_name);
dcp.new(project_name_odd, 'd', particles_dir, 'template', avg_odd,'masks', ...
    'default', 't', odd_tbl_file);

% Project settings
dvput(project_name_odd, 'd', 'mask', mask);
dvput(project_name_odd, 'd', 'cores', cores);
dvput(project_name_odd, 'd', 'mwa', mwa);
dvput(project_name_odd, 'd', 'ite_r1', ite_r1);
dvput(project_name_odd, 'd', 'cr_r1', cr_r1);
dvput(project_name_odd, 'd', 'cs_r1', cs_r1);
dvput(project_name_odd, 'd', 'ir_r1', ir_r1);
dvput(project_name_odd, 'd', 'is_r1', is_r1);
dvput(project_name_odd, 'd', 'rff_r1', rff_r1);
dvput(project_name_odd, 'd', 'rf_r1', rf_r1);
dvput(project_name_odd, 'd', 'dim_r1', dim_r1);
dvput(project_name_odd, 'd', 'lim_r1', lim_r1);
dvput(project_name_odd, 'd', 'limm_r1', limm_r1);
dvput(project_name_odd, 'd', 'nref_r1', nref_r1);
dvput(project_name_odd, 'd', 'high_r1', high_r1);
dvput(project_name_odd, 'd', 'low_r1', low_r1);
dvput(project_name_odd, 'd', 'sym_r1', sym_r1);
dvput(project_name_odd, 'd', 'dst', dst);
dvput(project_name_odd, 'd', 'gpus', gpus);

dvcheck(project_name_odd);
dvunfold(project_name_odd);

%% Create even project
project_name_even = sprintf('%s_even', project_name);
dcp.new(project_name_even, 'd', particles_dir, 'template', avg_even,'masks', ...
    'default', 't', even_tbl_file);

% Project settings
dvput(project_name_even, 'd', 'mask', mask);
dvput(project_name_even, 'd', 'cores', cores);
dvput(project_name_even, 'd', 'mwa', mwa);
dvput(project_name_even, 'd', 'ite_r1', ite_r1);
dvput(project_name_even, 'd', 'cr_r1', cr_r1);
dvput(project_name_even, 'd', 'cs_r1', cs_r1);
dvput(project_name_even, 'd', 'ir_r1', ir_r1);
dvput(project_name_even, 'd', 'is_r1', is_r1);
dvput(project_name_even, 'd', 'rff_r1', rff_r1);
dvput(project_name_even, 'd', 'rf_r1', rf_r1);
dvput(project_name_even, 'd', 'dim_r1', dim_r1);
dvput(project_name_even, 'd', 'lim_r1', lim_r1);
dvput(project_name_even, 'd', 'limm_r1', limm_r1);
dvput(project_name_even, 'd', 'nref_r1', nref_r1);
dvput(project_name_even, 'd', 'high_r1', high_r1);
dvput(project_name_even, 'd', 'low_r1', low_r1);
dvput(project_name_even, 'd', 'sym_r1', sym_r1);
dvput(project_name_even, 'd', 'dst', dst);
dvput(project_name_even, 'd', 'gpus', gpus);

dvcheck(project_name_even);
dvunfold(project_name_even);
