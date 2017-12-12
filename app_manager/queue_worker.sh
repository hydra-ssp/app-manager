#!/bin/bash
#
# (c) Copyright 2013, 2014, University of Manchester
#
# HydraPlatform is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HydraPlatform is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HydraPlatform.  If not, see <http://www.gnu.org/licenses/>
export LD_LIBRARY_PATH=/Applications/GAMS24.8/sysdir/
export DYLD_LIBRARY_PATH=/Applications/GAMS24.8/sysdir/
echo $LD_LIBRARY_PATH

QUEUEROOT=~/.hydra/apps/queue

QUEUEDDIR=queued
RUNNINGDIR=running
FINISHEDDIR=finished
FAILEDDIR=failed
TMPDIR=tmp
MODELDIR=model


echo "Starting Job Queue ..."

while true
do

    QJOBS=$(ls $QUEUEROOT/$QUEUEDDIR)

    NJOBS=${#QJOBS}

    if [ $NJOBS -eq 0 ];
    then
#        echo "Waiting for jobs ..."
        sleep 10
    fi

    for JOB in $QJOBS
    do
        date '+%F %T %Z'
        echo $JOB
        mv $QUEUEROOT/$QUEUEDDIR/$JOB $QUEUEROOT/$TMPDIR/$JOB

        JOBID=$(echo $JOB | python -c 'print raw_input().replace(".job", "")')

        #Identify the line in the file where the job is actuallu instatnitated. Assume that a '-m' argument is included, indicating that a model is being run.
        JOBCALL=$(cat $QUEUEROOT/$TMPDIR/$JOB | grep " \-m ")
        echo ${JOBCALL}

        mv $QUEUEROOT/$TMPDIR/$JOB $QUEUEROOT/$RUNNINGDIR
        
        #If the model path exists, create a new script, replacing the path
        #with a new path, symlinked to the old path. This will ensure logs are maintained
        #on a job-by-job basis.
        if [ -z "${JOBCALL}" ];
        then
            . $QUEUEROOT/$RUNNINGDIR/$JOB
        else
            echo "Found an -m argument. Building symlink and putting original job into the 'original' folder"
            #Extract the path to the model being run (assume the -m flag stands for 'model')
            MODELPATH=$(echo $JOBCALL |  python -c 'x = raw_input().split(" "); print (x[x.index("-m")+1]).replace("'"'"'", "")')

            #Identify the file name of the model
            MODELCONTAINER=$(echo $MODELPATH | python -c 'import os; print os.sep.join(raw_input().split(os.sep)[:-1]).replace("'"'"'", "")')
            MODELFILE=$(echo $MODELPATH | python -c 'import os; print raw_input().split(os.sep)[-1].replace("'"'"'", "")')
            echo $MODELFILE

            
            #Create a place for the runnable model run script to be placed
            if [ ! -d $QUEUEROOT/$MODELDIR/$JOBID ];
            then
                echo File doesnt exist
                mkdir $QUEUEROOT/$MODELDIR/$JOBID
            fi
            
            #Avoid cross-contamination of runs by removing all files from the model run folder
            rm $QUEUEROOT/$MODELDIR/$JOBID/*
            
            ln -s $MODELPATH $QUEUEROOT/$MODELDIR/$JOBID/$MODELFILE
            
            TXT_INPUTS=$(ls $MODELCONTAINER/*.txt)
            echo $TXT_INPUTS

            for TXTINPUT in $TXT_INPUTS
            do
                    TXTFILE=$(echo $TXTINPUT | python -c 'import os; print raw_input().split(os.sep)[-1].replace("'"'"'", "")')
                    echo $TXTFILE
                    ln -s $TXTINPUT $QUEUEROOT/$MODELDIR/$JOBID/$TXTFILE
            done

                #Remove the reference to the actual model run in the script and replace it with the symlink.
                NEWCMD=$(echo $JOBCALL"__"$QUEUEROOT/$MODELDIR/$JOBID/$MODELFILE | python -c 'x = raw_input().split("__"); y = x[0].split(" "); i = y.index("-m"); y[i+1]=x[1]; print (" ".join(y))')
                echo $NEWCMD >> $QUEUEROOT/$RUNNINGDIR/$JOB.amended
                echo "Running amended run file" $QUEUEROOT/$RUNNINGDIR/$JOB.amended

                . $QUEUEROOT/$RUNNINGDIR/$JOB.amended
                STATUS=$?

                echo "Removing amended run file"
                rm $QUEUEROOT/$RUNNINGDIR/$JOB.amended

                if [ $STATUS -ne 0 ];
                then
                    mv $QUEUEROOT/$RUNNINGDIR/$JOB $QUEUEROOT/$FAILEDDIR/
                else
                    mv $QUEUEROOT/$RUNNINGDIR/$JOB $QUEUEROOT/$FINISHEDDIR/
                fi
                date '+%F %T %Z'
                echo "Waiting for jobs ..."

        fi
    
    done

done
