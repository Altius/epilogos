from sys import argv
import numpy as np
from os import remove
from pathlib import Path
from time import time

def main(outputDirectory, storedExpInput, fileTag, verbose):
    if verbose: tTotal = time()

    outputDirPath = Path(outputDirectory)
    storedExpPath = Path(storedExpInput)

    # Loop over all the expected value arrays and add them up
    expFreqFileCount = 0
    expFreqArr = np.zeros((1,1))
    for file in outputDirPath.glob("temp_exp_freq_{}_*.npy".format(fileTag)):
        if expFreqFileCount == 0:
            expFreqArr = np.load(file, allow_pickle=False)
        else:
            expFreqArr += np.load(file, allow_pickle=False)
        expFreqFileCount += 1
    
    # Clean up temp files
    for file in outputDirPath.glob("temp_exp_freq_*.npy"):
        remove(file)

    # normalize expected frequency array
    expFreqArr = (expFreqArr / np.sum(expFreqArr)).astype(np.float32)

    np.save(storedExpPath, expFreqArr, allow_pickle=False)

    print("Total Time:", time() - tTotal) if verbose else print("    [Done]")

# Helper for slurm to send boolean values
def strToBool(string):
    if string == 'True':
        return True
    elif string == 'False':
        return False
    else:
        raise ValueError("Invalid boolean string")

if __name__ == "__main__":
    main(argv[1], argv[2], argv[3], strToBool(argv[4]))

