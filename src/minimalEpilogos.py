import numpy as np
from pathlib import Path
from pathlib import PurePath
import click
import computeEpilogosExpected
import computeEpilogosExpectedCombination
import computeEpilogosScores
import computeEpilogosWrite

@click.command()
@click.option("-f", "--file-directory", "fileDirectory", type=str, required=True, multiple=True, help="Path to directory that contains files to read from (All files in this directory will be read in)")
@click.option("-o", "--output-directory", "outputDirectory", type=str, required=True, multiple=True, help="Output Directory (CANNOT be the same as input directory)\n")
@click.option("-s", "--state-model", "numStates", type=int, required=True, multiple=True, help="Number of states in chromatin state model")
@click.option("-l", "--saliency-level", "saliency", type=int, default=[1], show_default=True, multiple=True, help="Desired saliency level (1, 2, or 3)")
@click.option("-m", "--mode-of-operation", "modeOfOperation", type=click.Choice(["bg", "s", "both"]), default=["both"], show_default=True, multiple=True, help="bg for background, s for scores, both for both")
@click.option("-b", "--background-directory", "expFreqDir", type=str, default=["null"], multiple=True, help="Path to where the background frequency array is read from (-m s) or written to (-m bg, -m both) [default: output-directory]")
@click.option("-c", "--num-cores", "numProcesses", type=int, default=[0], multiple=True, help="The number of cores to run on [default: 0 = Uses all cores]")
def main(fileDirectory, outputDirectory, numStates, saliency, modeOfOperation, expFreqDir, numProcesses):
    """
    This script computes scores for chromatin states across the genome.
    """

    # Handling case if user inputs flag multiples times
    if len(fileDirectory) > 1:
        raise ValueError("Too many [-f, --file-directory] arguments provided")
    elif len(outputDirectory) > 1:
        raise ValueError("Too many [-o, --output-directory] arguments provided")
    elif len(numStates) > 1:
        raise ValueError("Too many [-s, --state-model] arguments provided")
    elif len(saliency) > 1:
        raise ValueError("Too many [-l, --saliency-level] arguments provided")
    elif len(modeOfOperation) > 1:
        raise ValueError("Too many [-m, --mode-of-operation] arguments provided")
    elif len(expFreqDir) > 1:
        raise ValueError("Too many [-b, --background-directory] arguments provided")
    elif len(numProcesses) > 1:
        raise ValueError("Too many [-c, --num-cores] arguments provided")
    fileDirectory = fileDirectory[0]
    outputDirectory = outputDirectory[0]
    numStates = numStates[0]
    saliency = saliency[0]
    modeOfOperation = modeOfOperation[0]
    expFreqDir = expFreqDir[0]
    numProcesses = numProcesses[0]
        
    dataFilePath = Path(fileDirectory)
    outputDirPath = Path(outputDirectory)

    print()
    print("Input Directory =", dataFilePath)
    print("State Model =", numStates)
    print("Saliency level =", saliency)
    print("Output Directory =", outputDirPath)
    print("Mode of Operation =", modeOfOperation)
    print("Background Directory =", expFreqDir)

    # If user does not specificy a directory to look for expected frequencies default the output directory
    if expFreqDir == "null":
        expFreqDir = outputDirectory

    # Making paths absolute
    if not PurePath(outputDirPath).is_absolute():
        outputDirPath = Path.cwd() / outputDirPath
    if not PurePath(dataFilePath).is_absolute():
        dataFilePath = Path.cwd() / dataFilePath

    # For making sure all files are consistently named
    fileTag = "{}_saliency{}".format(dataFilePath.name, saliency)

    if saliency != 1 and saliency != 2 and saliency != 3:
        print("\nERROR: Ensure that saliency metric is either 1, 2, or 3\n")
        return

    # Check that paths are valid before doing anything
    if not dataFilePath.exists() or not dataFilePath.is_dir():
        print("\nERROR: Given file path does not exist or is not a directory\n")
        return

    if not list(dataFilePath.glob("*")):
        print("\nERROR: Ensure that file directory is not empty\n")
        return

    # If the output directory does not exist yet, make it for the user 
    if not outputDirPath.exists():
        outputDirPath.mkdir(parents=True)
    
    if not outputDirPath.is_dir():
        print("\nERROR: Output directory is not a directory\n")
        return

    if numProcesses < 0:
        print("\nERROR: Number of cores must be positive or zero (0 means use all cores)\n")
        return
    elif numProcesses == 0:
        numTasks = "--exclusive"
    else:
        numTasks = "--ntasks={}".format(numProcesses)

    # For slurm output and error later
    (outputDirPath / ".out/").mkdir(parents=True, exist_ok=True)
    (outputDirPath / ".err/").mkdir(parents=True, exist_ok=True)

    # Path for storing/retrieving the expected frequency array
    # Expected frequency arrays are stored according to path of the input file directory
    storedExpPath = Path(expFreqDir) / "exp_freq_{}.npy".format(fileTag)
    print("\nBackground Frequency Array Location:", storedExpPath)

    # Only calculate the expected frequencies if user asks for it, otherwise just load from where the user said
    if modeOfOperation == "s":
        try:
            expFreqArr = np.load(storedExpPath, allow_pickle=False)
        except IOError:
            print("\nERROR: Could not load stored expected value array.\n\tPlease check that the directory is correct or that the file exists\n")
            return
    else:
        print("\nCalculating Per Datafile Background Frequency Arrays...")
        for file in dataFilePath.glob("*"):
            if file.name.split(".")[1] == "genome":
                continue
            if not file.is_dir():
                computeEpilogosExpected.main(file, numStates, saliency, outputDirPath, fileTag, numProcesses)

        print("\nCombining Per Datafile Background Frequency Arrays....")
        computeEpilogosExpectedCombination.main(outputDirPath, storedExpPath, fileTag)

    if modeOfOperation == "s" or modeOfOperation == "both":
        print("\nCalculating Per Datafile Scores...")
        for file in dataFilePath.glob("*"):
            if file.name.split(".")[1] == "genome":
                continue
            if not file.is_dir():
                computeEpilogosScores.main(file, numStates, saliency, outputDirPath, storedExpPath, fileTag, numProcesses)

        print("\nWriting to Score Files....")
        for file in dataFilePath.glob("*"):
            if file.name.split(".")[1] == "genome":
                continue
            if not file.is_dir():
                computeEpilogosWrite.main(file, numStates, outputDirPath, fileTag)

    
if __name__ == "__main__":
    main()