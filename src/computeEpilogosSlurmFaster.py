import gzip
import numpy as np
from pathlib import Path
import pandas as pd
import time
import click
import os
import subprocess
from pathlib import PurePath

@click.command()
@click.option("-f", "--file-directory", "fileDirectory", type=str, required=True, help="Path to directory that contains files to read from (Please ensure that this directory contains only files you want to read from)")
@click.option("-m", "--state-model", "numStates", type=int, required=True, help="Number of states in chromatin state model")
@click.option("-l", "--saliency-level", "saliency", type=int, required=True, help="Saliency level (1, 2, or 3)")
@click.option("-o", "--output-directory", "outputDirectory", type=str, required=True, help="Output Directory")
@click.option("-e", "--calculate-expected", "calcExp", is_flag=True, help="[Flag] Just calculate the expected frequencies")
@click.option("-s", "--calculate-scores", "calcScores", is_flag=True, help="[Flag] Use previously stored expected frequency array to calculate scores")
@click.option("-d", "--expected-directory", "expFreqDir", type=str, required=True, help="Path to the expected frequency array (Used in conjunction with either '-e' or '-s')")
def main(fileDirectory, numStates, saliency, outputDirectory, calcExp, calcScores, expFreqDir):
    tTotal = time.time()
    dataFilePath = Path(fileDirectory)
    outputDirPath = Path(outputDirectory)

    fileTag = "_".join(str(dataFilePath).split("/")[-5:])

    print("FILETAG: ", fileTag)
    print("CWD: ", Path.cwd())
    print("fileDirectory=", dataFilePath)
    print("numStates=", numStates)
    print("saliency=", saliency)
    print("outputDirectory=", outputDirPath)
    print("calcExp=", calcExp)
    print("calcScores=", calcScores)
    print("expFreqDir=", expFreqDir)

    if not calcExp and not calcScores:
        print()
        print("ERROR: Please at least one of the --calculate-expected (-e) or --calculate-scores (-s) flags")
        print()
        return

    if not PurePath(outputDirPath).is_absolute():
        outputDirPath = Path.cwd() / outputDirPath
        print("OUTPUTPATH: ", outputDirPath)

    if not PurePath(dataFilePath).is_absolute():
        dataFilePath = Path.cwd() / dataFilePath
        print("FILE PATH: ", dataFilePath)

    # Check that paths are valid before doing anything
    if not dataFilePath.exists() or not dataFilePath.is_dir():
        print()
        print("ERROR: Given file path does not exist or is not a directory")
        print()
        return

    if not list(dataFilePath.glob("*")):
        print()
        print("ERROR: Ensure that file directory is not empty")
        print()
        return

    # If the output directory does not exist yet, make it for the user 
    if not outputDirPath.exists():
        outputDirPath.mkdir(parents=True)
    
    # For slurm output and error later
    (outputDirPath / ".out/").mkdir(parents=True, exist_ok=True)
    (outputDirPath / ".err/").mkdir(parents=True, exist_ok=True)

    if not outputDirPath.is_dir():
        print("ERROR: Output directory is not a directory")
        return

    # Calculate the number of epigenomes (just read one line of one of the data files)
    for x in dataFilePath.glob("*"):
        numEpigenomes = pd.read_table(x, header=None, sep="\t", nrows=1).shape[1] - 3
        break

    # Path for storing/retrieving the expected frequency array
    # Expected frequency arrays are stored according to path of the input file directory
    expFreqFilename = "exp_freq_{}.npy".format(fileTag)
    storedExpPath = Path(expFreqDir) / expFreqFilename

    # Finding the location of the .py files that must be run
    if PurePath(__file__).is_absolute():
        pythonFilesDir = Path(__file__).parents[0]
    else:
        pythonFilesDir = Path.cwd() / Path(__file__).parents[0]

    # Check if user wants to calculate it
    if not calcExp:
        try:
            expFreqArr = np.load(storedExpPath, allow_pickle=False)
        except IOError:
            print("ERROR: Could not load stored expected value array.\n\tPlease check that the directory is correct or that the file exists")
    else:     
        expJobIDArr = []   
        print()
        print("Calculating expected frequencies....")
        for file in dataFilePath.glob("*"):
            if not file.is_dir():
                filename = file.name.split(".")[0]
                jobName = "exp_freq_calc_{}_{}".format(fileTag, filename)
                jobOutPath = outputDirPath / (".out/" + jobName + ".out")
                jobErrPath = outputDirPath / (".err/" + jobName + ".err")

                # Creating the out and err files for the batch job
                if jobOutPath.exists():
                    os.remove(jobOutPath)
                if jobErrPath.exists():
                    os.remove(jobErrPath)
                try:
                    jout = open(jobOutPath, 'x')
                    jout.close()
                    jerr = open(jobErrPath, 'x')
                    jerr.close()
                except FileExistsError:
                    # This error should never occur because we are deleting the files first
                    print("ERROR: sbatch '.out' or '.err' file already exists")

                computeExpectedPy = pythonFilesDir / "computeEpilogosExpected.py"

                pythonCommand = "python {} {} {} {} {} {}".format(computeExpectedPy, file, numStates, saliency, outputDirPath, fileTag)

                slurmCommand = "sbatch --job-name={}.job --output={} --error={} --nodes=1 --ntasks=1 --wrap='{}'".format(jobName, jobOutPath, jobErrPath, pythonCommand)

                sp = subprocess.run(slurmCommand, shell=True, check=True, universal_newlines=True, stdout=subprocess.PIPE)

                if not sp.stdout.startswith("Submitted batch"):
                    print("ERROR: sbatch not submitted correctly")
                
                expJobIDArr.append(int(sp.stdout.split()[-1]))

        # Combining all the different chromosome expected frequency arrays into one
        # create a string for slurm dependency to work
        jobIDStrComb = str(expJobIDArr).strip('[]').replace(" ", "")

        print()
        print("Combining expected frequencies....")

        jobName = "exp_freq_comb_{}".format(fileTag)
        jobOutPath = outputDirPath / (".out/" + jobName + ".out")
        jobErrPath = outputDirPath / (".err/" + jobName + ".err")

        # Creating the out and err files for the batch job
        if jobOutPath.exists():
            os.remove(jobOutPath)
        if jobErrPath.exists():
            os.remove(jobErrPath)
        try:
            jout = open(jobOutPath, 'x')
            jout.close()
            jerr = open(jobErrPath, 'x')
            jerr.close()
        except FileExistsError:
            # This error should never occur because we are deleting the files first
            print("ERROR: sbatch '.out' or '.err' file already exists")

        computeExpectedCombinationPy = pythonFilesDir / "computeEpilogosExpectedCombination.py"

        pythonCommand = "python {} {} {} {}".format(computeExpectedCombinationPy, outputDirPath, fileTag, storedExpPath)

        slurmCommand = "sbatch --dependency=afterok:{} --job-name={}.job --output={} --error={} --nodes=1 --ntasks=1 --wrap='{}'".format(jobIDStrComb, jobName, jobOutPath, jobErrPath, pythonCommand)

        sp = subprocess.run(slurmCommand, shell=True, check=True, universal_newlines=True, stdout=subprocess.PIPE)

        if not sp.stdout.startswith("Submitted batch"):
            print("ERROR: sbatch not submitted correctly")
        
        combinationJobID = int(sp.stdout.split()[-1])

    if calcScores:
        # Calculate the observed frequencies and scores
        print()
        print("Calculating Scores....")
        scoreJobIDArr = []
        for file in dataFilePath.glob("*"):
            if not file.is_dir():
                filename = file.name.split(".")[0]
                jobName = "score_calc_{}_{}".format(fileTag, filename)
                jobOutPath = outputDirPath / (".out/" + jobName + ".out")
                jobErrPath = outputDirPath / (".err/" + jobName + ".err")

                # Creating the out and err files for the batch job
                if jobOutPath.exists():
                    os.remove(jobOutPath)
                if jobErrPath.exists():
                    os.remove(jobErrPath)
                try:
                    jout = open(jobOutPath, 'x')
                    jout.close()
                    jerr = open(jobErrPath, 'x')
                    jerr.close()
                except FileExistsError:
                    # This error should never occur because we are deleting the files first
                    print("ERROR: sbatch '.out' or '.err' file already exists")
                
                computeScorePy = pythonFilesDir / "computeEpilogosScores.py"

                pythonCommand = "python {} {} {} {} {} {} {}".format(computeScorePy, file, numStates, saliency, outputDirPath, storedExpPath, fileTag)
                slurmCommand = "sbatch --dependency=afterok:{} --job-name={}.job --output={} --error={} --nodes=1 --ntasks=1 --mem-per-cpu=8000 --wrap='{}'".format(combinationJobID, jobName, jobOutPath, jobErrPath, pythonCommand)

                sp = subprocess.run(slurmCommand, shell=True, check=True, universal_newlines=True, stdout=subprocess.PIPE)

                if not sp.stdout.startswith("Submitted batch"):
                    print("ERROR: sbatch not submitted correctly")
                
                scoreJobIDArr.append(int(sp.stdout.split()[-1]))

        # WRITING TO SCORE FILE
        print()
        print("Writing to score files....")
        # create a string for slurm dependency to work
        jobIDStrWrite = str(scoreJobIDArr).strip('[]').replace(" ", "")

        jobName = "write_{}".format(fileTag)
        jobOutPath = outputDirPath / (".out/" + jobName + ".out")
        jobErrPath = outputDirPath / (".err/" + jobName + ".err")

        # Creating the out and err files for the batch job
        if jobOutPath.exists():
            os.remove(jobOutPath)
        if jobErrPath.exists():
            os.remove(jobErrPath)
        try:
            jout = open(jobOutPath, 'x')
            jout.close()
            jerr = open(jobErrPath, 'x')
            jerr.close()
        except FileExistsError:
            # This error should never occur because we are deleting the files first
            print("ERROR: sbatch '.out' or '.err' file already exists")

        computeExpectedWritePy = pythonFilesDir / "computeEpilogosWriteFaster.py"

        pythonCommand = "python {} {} {} {}".format(computeExpectedWritePy, fileTag, outputDirPath, numStates)

        slurmCommand = "sbatch --dependency=afterok:{} --job-name={}.job --output={} --error={} --nodes=1 --ntasks=1 --mail-type=END --mail-user=jquon@altius.org --mem-per-cpu=8000 --wrap='{}'".format(jobIDStrWrite, jobName, jobOutPath, jobErrPath, pythonCommand)

        sp = subprocess.run(slurmCommand, shell=True, check=True, universal_newlines=True, stdout=subprocess.PIPE)

        if not sp.stdout.startswith("Submitted batch"):
            print("ERROR: sbatch not submitted correctly")

if __name__ == "__main__":
    main()