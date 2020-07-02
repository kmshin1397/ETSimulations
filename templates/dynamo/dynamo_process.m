%% dynamo_process.m

% The dynamo_process.m script attempts to automate the process of setting 
% up a Dynamo sub-tomogram averaging project starting from a .doc and .tbl
% file. 

% Kyung Min Shin, Caltech, 2020

%% Input parameters
basename = "";
doc_file = "";
tbl_file = "";
particles_dir = "";
box_size = 72;
num_workers = 12;

%% Process table
dtcrop(doc_file, tbl_file, particles_dir, box_size, 'mw', num_workers);
azrand=dynamo_table_randomize_azimuth(tbl_file);
azrand_file = sprintf('%s_azrand.tbl', basename);
dwrite(azrand, azrand_file);
dynamo_table_eo(azrand_file, 'disk', 1);

even_tbl_file = sprintf('%s_azrand_even.tbl', basename);
az_e = daverage(particles_dir, 't', even_tbl_file, 'fcompensate', 1, 'mw', num_workers);
dwrite(az_e.average,'manual/manual_avg_azrand_even.em');