$batchruntomo -StandardInput
CheckFile	batchETSimulations.cmds
CPUMachineList	localhost:12
NiceValue	15
EtomoDebug	0
StartingStep	0.0
EndingStep	1.0
