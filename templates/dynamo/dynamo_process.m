%% dynamo_process.m

% The dynamo_process.m script attempts to automate the process of setting 
% up a Dynamo sub-tomogram averaging project starting from a .doc and .tbl
% file. 

% Kyung Min Shin, Caltech, 2020

% NOTE: The below section comment line is used by dynamo_processor.py to identify
% the section of input parameters to fill in automatically, so you should
% not remove it.
%% Input parameters
apix = '';
basename = '';
doc_file = '';
tbl_file = '';
particles_dir = '';
box_size = 72;
project_name = '';
mask = '';
cores = 1;
num_workers = '';
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
ite_r2 = '';
cr_r2 = '';
cs_r2 = '';
ir_r2 = '';
is_r2 = '';
rff_r2 = '';
rf_r2 = '';
dim_r2 = '';
lim_r2 = '';
limm_r2 = '';
nref_r2 = '';
high_r2 = '';
low_r2 = '';
sym_r2 = '';
dst = '';
gpus = '';
invert_particles = 1;

% NOTE: The below comment line is used by dynamo_processor.py to identify
% the end of the input parameters section, so you should not remove it.
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
avg_even = 'averages/init_avg_azrand_even.em';
dwrite(az_e.average, avg_even);

odd_tbl_file = sprintf('%s_azrand_odd.tbl', basename);
az_o = daverage(particles_dir, 't', odd_tbl_file, 'fcompensate', 1, ...
    'mw', num_workers);
avg_odd = 'averages/init_avg_azrand_odd.em';
dwrite(az_o.average, avg_odd);

%% Create odd project
project_name_odd = sprintf('odd_%s', project_name);
dcp.new(project_name_odd, 'd', particles_dir, 'template', avg_odd,'masks', ...
    'default', 't', odd_tbl_file);

% Project settings
dvput(project_name_odd, 'd', 'mask', mask);
dvput(project_name_odd, 'd', 'cores', cores);
dvput(project_name_odd, 'd', 'num_workers', num_workers);
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
project_name_even = sprintf('even_%s', project_name);
dcp.new(project_name_even, 'd', particles_dir, 'template', avg_even,'masks', ...
    'default', 't', even_tbl_file);

% Project settings
dvput(project_name_even, 'd', 'mask', mask);
dvput(project_name_even, 'd', 'cores', cores);
dvput(project_name_even, 'd', 'num_workers', num_workers);
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


%% Start the even & odd jobs

even_job=[project_name_even,'.m'];
odd_job=[project_name_odd,'.m'];
run(even_job);
run(odd_job);


%% Make FSC curve
% Make even and odd averages with all the particles
even_avg = [project_name_even, '/results/ite_0001/averages/even_avg.em'];
odd_avg = [project_name_odd, '/results/ite_0001/averages/odd_avg.em'];

even_table = dread([project_name_even, '/results/ite_0001/averages/refined_table_ref_001_ite_0001.tbl']);
odd_table = dread([project_name_odd, '/results/ite_0001/averages/refined_table_ref_001_ite_0001.tbl']);

even = daverage(particles_dir, 't', even_table, 'fcompensate', 1, 'mw', num_workers);
dwrite(even.average, even_avg);

odd = daverage(particles_dir, 't', odd_table, 'fcompensate', 1, 'mw', num_workers);
dwrite(odd.average, odd_avg);

% Align the two averages with each other
sal = dalign(odd_avg, even_avg, 'cr', 0, 'cs', 1, 'ir', 60, 'is', 1, 'rf', 2, 'rff', 2, ...
    'dim', 128, 'limm', 1, 'lim', [2 2 2]);
dwrite(sal.aligned_particle, [project_name_odd, '/results/ite_0001/averages/odd_avg_aligned2even.em']);
odd_aligned_to_even_table = dynamo_table_rigid(odd_table, sal.Tp);
dwrite(odd_aligned_to_even_table, ...
    [project_name_odd, '/results/ite_0001/averages/refined_table_ref_001_ite_0001_aligned_to_even.tbl']);
full_tbl = dynamo_table_merge({even_table, odd_aligned_to_even_table});
dwrite(full_tbl, [project_name_odd, '/results/ite_0001/averages/full.tbl']);
full_avg = daverage(particles_dir, 't', full_tbl, 'fcompensate', 1, 'mw', 24);
dwrite(full_avg.average, [project_name_odd, '/results/ite_0001/averages/full_avg.em']);

% Calculate fsc
dfsc(even_avg, odd_avg, 'nshells', 32, 'apix', apix, 'show', 1, ...
    'o', [project_name_odd, '/results/ite_0001/averages/fsc_alignedeo.txt'], 'mask', mask);

% Save the fsc curve
savefig([project_name_odd, '/results/ite_0001/averages/fsc.fig']);