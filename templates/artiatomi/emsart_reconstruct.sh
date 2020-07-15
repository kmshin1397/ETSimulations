#!/bin/bash
# Script to run EmSART reconstructions for a dataset

T="$(date +%s%N)"
emsart_path="EmSART"
for f in /data/kshin/T4SS_sim/PDB/c4/IMOD/T4SS_*
do
	echo "==================================================="
	cd $f
	config_file="EmSART_HR.cfg"
	$emsart_path -u $config_file 
	echo "==================================================="
done

#Time interval in nanoseconds
T="$(($(date +%s%N)-T))"
# Seconds
S="$((T/1000000000))"
# Milliseconds
M="$((T/1000000))"

printf "Completed tomogram reconstructions in %02d days %02d hrs %02d min %02d.%03d sec\n" "$((S/86400))" "$((S/3600%24))" "$((S/60%60))" "$((S%60))" "${M}" | mail -s "EmSART Status" kshin@caltech.edu
