import numpy as np
import sys
from pathlib import Path
import math
import pandas as pd
import time
import operator as op
from functools import reduce
import multiprocessing
import itertools
from contextlib import closing

def main(filename, numStates, saliency, outputDirPath, fileTag, numProcesses):
    dataFilePath = Path(filename)
    outputDirPath = Path(outputDirPath)

    ###################################################
    ##
    ##   chrName is hacky, find a better way later
    ##
    ####################################################
    chrName  = dataFilePath.name.split("_")[-1].split(".")[0]

    # Get the genome file
    genomeFileList = list(dataFilePath.parents[0].glob("*.genome"))
    if len(genomeFileList) > 1:
        raise IOError("Too many '.genome' files provided")
    elif len(genomeFileList) < 1:
        raise IOError("No '.genome' file provided")

    # Read line by line until we are on correct chromosome, then read out number of bp
    for genomeFile in genomeFileList:
        with open(genomeFile, "r") as gf:
            line = gf.readline()
            while chrName not in line:
                line = gf.readline
            basePairs = int(line.split()[1])

    totalRows = int(basePairs / 200)

    # If user doesn't want to choose number of cores use as many as available
    if numProcesses == 0:
        numProcesses = multiprocessing.cpu_count()

    # Split the rows up according to the number of cores we have available
    rowList = []
    for i in range(numProcesses):
        rowsToCalculate = (i * totalRows // numProcesses, (i+1) * totalRows // numProcesses)
        rowList.append(rowsToCalculate)

    determineSaliency(saliency, dataFilePath, rowList, totalRows, numStates, outputDirPath, fileTag, chrName, numProcesses)


def determineSaliency(saliency, dataFilePath, rowList, totalRows, numStates, outputDirPath, fileTag, chrName, numProcesses):
    if saliency == 1:
        s1Exp(dataFilePath, rowList, totalRows, numStates, outputDirPath, fileTag, chrName, numProcesses)
    elif saliency == 2:
        s2Exp(dataFilePath, rowList, totalRows, numStates, outputDirPath, fileTag, chrName, numProcesses)
    elif saliency == 3:
        s3Exp(dataFilePath, rowList, totalRows, numStates, outputDirPath, fileTag, chrName, numProcesses)
    else:
        print("Inputed saliency value not supported")
        return


# Function that calculates the expected frequencies for the S1 metric
def s1Exp(dataFilePath, rowList, totalRows, numStates, outputDirPath, fileTag, chrName, numProcesses):
    print("NUM PROCESSES:", numProcesses)
    
    # Start the processes
    with closing(multiprocessing.Pool(numProcesses)) as pool:
        results = pool.starmap(s1Calc, zip(itertools.repeat(dataFilePath), rowList, itertools.repeat(numStates)))
    pool.join()

    # Sum all the expected frequency arrays from the seperate processes and normalize by dividing by numRows
    expFreqArr = np.sum(results, axis=0) / totalRows

    storeExpArray(expFreqArr, outputDirPath, fileTag, chrName)


# Function that reads in data and calculates the expected frequencies for the S2 metric over a chunk of the data
def s1Calc(dataFilePath, rowsToCalculate, numStates):
    # Reading in the data
    print("\nReading data from file...")
    tRead = time.time()
    dataDF = pd.read_table(dataFilePath, skiprows=rowsToCalculate[0], nrows=rowsToCalculate[1]-rowsToCalculate[0], header=None, sep="\t")
    print("    Time: ", time.time() - tRead)

    # Converting to a np array for faster functions
    print("Converting to numpy array...")
    tConvert = time.time()
    dataArr = dataDF.iloc[:,3:].to_numpy(dtype=int) - 1 
    print("    Time: ", time.time() - tConvert)

    multiprocessRows, numCols = dataArr.shape

    expFreqArr = np.zeros(numStates, dtype=np.float32)

    # Simply count each state rowwise, dividing by 
    uniqueStates, stateCounts = np.unique(dataArr, return_counts=True)
    for i, state in enumerate(uniqueStates):
        expFreqArr[state] += stateCounts[i] / numCols

    return expFreqArr

# Function that deploys the processes used to calculate the expected frequencies for the s2 metric. Also calls function to store expected frequency
def s2Exp(dataFilePath, rowList, totalRows, numStates, outputDirPath, fileTag, chrName, numProcesses):
    print("NUM PROCESSES:", numProcesses)

    if (sys.version_info < (3, 8)):
        print("\nFor maximum efficiency please update python to version 3.8 or later")
        print("NOTE: The code will still run in a lower version, but will be slightly slower\n")

    # Start the processes
    with closing(multiprocessing.Pool(numProcesses)) as pool:
        results = pool.starmap(s2Calc, zip(itertools.repeat(dataFilePath), rowList, itertools.repeat(numStates)))
    pool.join()

    # Sum all the expected frequency arrays from the seperate processes and normalize by dividing by numRows
    expFreqArr = np.sum(results, axis = 0) / totalRows

    storeExpArray(expFreqArr, outputDirPath, fileTag, chrName)


# Function that reads in data and calculates the expected frequencies for the S2 metric over a chunk of the data
def s2Calc(dataFilePath, rowsToCalculate, numStates):
    # Reading in the data
    print("\nReading data from file...")
    tRead = time.time()
    dataDF = pd.read_table(dataFilePath, skiprows=rowsToCalculate[0], nrows=rowsToCalculate[1]-rowsToCalculate[0], header=None, sep="\t")
    print("    Time: ", time.time() - tRead)

    # Converting to a np array for faster functions
    print("Converting to numpy array...")
    tConvert = time.time()
    dataArr = dataDF.iloc[:,3:].to_numpy(dtype=int) - 1 
    print("    Time: ", time.time() - tConvert)

    multiprocessRows, numCols = dataArr.shape

    expFreqArr = np.zeros((numStates, numStates), dtype=np.float32)

    # SumOverRows: (Within a row, how many ways can you choose x and y to be together) / (how many ways can you choose 2 states)
    # SumOverRows: (Prob of choosing x and y)
    # Can choose x and y to be together x*y ways if different and n(n-1)/2 ways if same (where n is the number of times that x/y shows up)
    if (sys.version_info < (3, 8)):
        combinations = ncr(numCols, 2)
        for row in range(multiprocessRows):
            uniqueStates, stateCounts = np.unique(dataArr[row], return_counts=True)
            for i in range(len(uniqueStates)):
                for j in range(len(uniqueStates)):
                    if uniqueStates[i] > uniqueStates[j] or uniqueStates[i] < uniqueStates[j]:
                        expFreqArr[uniqueStates[i], uniqueStates[j]] += stateCounts[i] * stateCounts[j] / combinations / 2 # Extra 2 is to account for the symmetric matrix
                    elif uniqueStates[i] == uniqueStates[j]:
                        expFreqArr[uniqueStates[i], uniqueStates[j]] += ncr(stateCounts[i], 2) / combinations
    else:
        combinations = math.comb(numCols, 2)
        for row in range(multiprocessRows):
            uniqueStates, stateCounts = np.unique(dataArr[row], return_counts=True) 
            for i in range(len(uniqueStates)):
                for j in range(len(uniqueStates)):
                    if uniqueStates[i] > uniqueStates[j] or uniqueStates[i] < uniqueStates[j]:
                        expFreqArr[uniqueStates[i], uniqueStates[j]] += stateCounts[i] * stateCounts[j] / combinations / 2 # Extra 2 is to account for the symmetric matrix
                    elif uniqueStates[i] == uniqueStates[j]:
                        expFreqArr[uniqueStates[i], uniqueStates[j]] += math.comb(stateCounts[i], 2) / combinations

    return expFreqArr

# Function that deploys the processes used to calculate the expected frequencies for the s3 metric. Also call function to store expected frequency
def s3Exp(dataFilePath, rowList, totalRows, numStates, outputDirPath, fileTag, chrName, numProcesses):
    print("NUM PROCESSES:", numProcesses)

    # Start the processes
    with closing(multiprocessing.Pool(numProcesses)) as pool:
        results = pool.starmap(s3Calc, zip(itertools.repeat(dataFilePath), rowList, itertools.repeat(numStates)))
    pool.join()

    # Read one line to determine numCols
    numCols = pd.read_table(dataFilePath, nrows=1, header=None, sep="\t").shape[1]

    # Sum all the expected frequency arrays from the seperate processes and normalize by dividing
    expFreqArr = np.sum(results, axis = 0) / (totalRows * numCols * (numCols - 1))

    storeExpArray(expFreqArr, outputDirPath, fileTag, chrName)

# Function that calculates the expected frequencies for the S3 metric over a chunk of the data
def s3Calc(dataFilePath, rowsToCalculate, numStates):
    # Reading in the data
    print("\nReading data from file...")
    tRead = time.time()
    dataDF = pd.read_table(dataFilePath, skiprows=rowsToCalculate[0], nrows=rowsToCalculate[1]-rowsToCalculate[0], header=None, sep="\t")
    print("    Time: ", time.time() - tRead)

    # Converting to a np array for faster functions
    print("Converting to numpy array...")
    tConvert = time.time()
    dataArr = dataDF.iloc[:,3:].to_numpy(dtype=int) - 1 
    print("    Time: ", time.time() - tConvert)

    multiprocessRows, numCols = dataArr.shape

    # Gives us everyway to combine the column numbers in numpy indexing form
    basePermutationArr = np.array(list(itertools.permutations(range(numCols), 2))).T

    expFreqArr = np.zeros((numCols, numCols, numStates, numStates), dtype=np.int32)
    
    # We tally a one for all the state/column combinations we observe (e.g. for state 18 in column 2 and state 15 in column 6 we would add one to index [5, 1, 17, 14])
    for row in range(multiprocessRows):
        expFreqArr[basePermutationArr[0], basePermutationArr[1], dataArr[row, basePermutationArr[0]], dataArr[row, basePermutationArr[1]]] += 1

    return expFreqArr

# Helper to store the expected frequency arrays
def storeExpArray(expFreqArr, outputDirPath, fileTag, chrName):
    # Creating a file path
    expFreqFilename = "temp_exp_freq_{}_{}.npy".format(fileTag, chrName)
    expFreqPath = outputDirPath / expFreqFilename

    np.save(expFreqPath, expFreqArr, allow_pickle=False)

# Helper to calculate combinations
def ncr(n, r):
    r = min(r, n-r)
    numer = reduce(op.mul, range(n, n - r, -1), 1)
    denom = reduce(op.mul, range(1, r + 1), 1)
    return numer // denom

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5], int(sys.argv[6]))