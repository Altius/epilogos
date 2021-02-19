from os import error
import numpy as np
import sys
from pathlib import Path
import math
import pandas as pd
import time
import numpy.ma as ma
import operator as op
from functools import reduce
import multiprocessing
import itertools
import ctypes as c
import gzip
from contextlib import closing

def main(file1, file2, numStates, saliency, outputDirPath, expFreqPath, fileTag, numProcesses, realOrNull):
    try:
        tTotal = time.time()

        file1Path = Path(file1)
        file2Path = Path(file2)
        outputDirPath = Path(outputDirPath)

        filename = file1Path.name.split(".")[0]

        if file1Path.name.endswith("gz"):
            with gzip.open(file1Path, "rb") as f:
                totalRows = sum(bl.count(b'\n') for bl in blocks(f))
        else:
            with open(file1Path, "rb") as f:
                totalRows = sum(bl.count(b'\n') for bl in blocks(f))

        # If user doesn't want to choose number of cores use as many as available
        if numProcesses == 0:
            numProcesses = multiprocessing.cpu_count()

        # Split the rows up according to the number of cores we have available
        rowList = []
        for i in range(numProcesses):
            rowsToCalculate = (i * totalRows // numProcesses, (i+1) * totalRows // numProcesses)
            rowList.append(rowsToCalculate)

        # Calculate the scores
        scoreArr1, scoreArr2 = determineSaliency(saliency, file1Path, file2Path, rowList, totalRows, numStates, expFreqPath, numProcesses, realOrNull)

        print("Calculating Raw Differences...")
        tDiff = time.time()
        diffArr = scoreArr1 - scoreArr2
        print("    Time:", time.time() - tDiff)

        # Only calculate the distances for the null data in this step
        if realOrNull.lower() == "null":
            print("Calculating Squared Euclidean Distance and Maximum Contributing Difference...")
            tDistance = time.time()
            diffSign = np.sign(np.sum(diffArr, axis=1))
            nullDistancesArr = np.sum(np.square(diffArr), axis=1) * diffSign
            print("    Time:", time.time() - tDistance)

        print("Writing output to disk...")
        tWrite = time.time()
        chrName = pd.read_table(file1Path, nrows=1, header=None, sep="\t").iloc[0, 0]
        # If it's the real data, we will just write the delta and calculate metrics in computeEpilogosPairwiseVisual
        # If it's the null data, we will just write the signed squared euclidean distances
        if realOrNull.lower() == "real":
            writeReal(diffArr, outputDirPath, fileTag, filename, chrName)
        elif realOrNull.lower() == "null":
            writeNull(nullDistancesArr, outputDirPath, fileTag, filename, chrName)
        else:
            raise ValueError("Could not determine if writing real or null data")
        print("    Time:", time.time() - tWrite)

        print("Total Time:", time.time() - tTotal)
    except OSError as err:
        if err.errno == 16:
            print("Warning: OSError 16 thrown. In testing we have found this does not effect the program output, but please check output file to be certain")
        else:
            print(err)
    except:
        print(sys.exc_info()[0])

# Helper function to determine the pick the correct saliency function
def determineSaliency(saliency, file1Path, file2Path, rowList, totalRows, numStates, expFreqPath, numProcesses, realOrNull):
    if saliency == 1:
        return s1Multi(file1Path, file2Path, rowList, totalRows, numStates, expFreqPath, numProcesses, realOrNull)
    elif saliency == 2:
        return s2Multi(file1Path, file2Path, rowList, totalRows, numStates, expFreqPath, numProcesses, realOrNull)
    elif saliency == 3:
        raise ValueError("A saliency value of 3 is not supported for pairwise comparison")
    else:
        raise ValueError("Inputed saliency value not supported")

def readInData(file1Path, file2Path, rowsToCalculate, realOrNull):
    # Read in the data
    if rowsToCalculate[0] == 0: print("Reading data from file 1..."); tRead1 = time.time()
    # Dont want to read in locations
    cols = range(3, pd.read_table(file1Path, nrows=1, header=None, sep="\t").shape[1])
    # Read using pd.read_table and convert to numpy array for faster calculation (faster than np.genfromtext())
    file1Arr = pd.read_table(file1Path, usecols=cols, skiprows=rowsToCalculate[0], nrows=rowsToCalculate[1]-rowsToCalculate[0], header=None, sep="\t").to_numpy(dtype=int) - 1
    if rowsToCalculate[0] == 0: print("    Time: ", time.time() - tRead1)

    if rowsToCalculate[0] == 0: print("Reading data from file 2..."); tRead2 = time.time()
    cols = range(3, pd.read_table(file2Path, nrows=1, header=None, sep="\t").shape[1])
    # Read using pd.read_table and convert to numpy array for faster calculation (faster than np.genfromtext())
    file2Arr = pd.read_table(file2Path, usecols=cols, skiprows=rowsToCalculate[0], nrows=rowsToCalculate[1]-rowsToCalculate[0], header=None, sep="\t").to_numpy(dtype=int) - 1
    if rowsToCalculate[0] == 0: print("    Time: ", time.time() - tRead2)

    if realOrNull.lower() == "real":
        return file1Arr, file2Arr
    elif realOrNull.lower() == "null":
        if rowsToCalculate[0] == 0: print("Shuffling input matrices..."); tShuffle = time.time()
        # Combining the arrays for per row shuffling
        combinedArr = np.concatenate((file1Arr, file2Arr), axis=1)

        # Row independent vectorized shuffling of the 2 arrays
        randomIndices = np.argsort(np.random.rand(*combinedArr.shape), axis=1)
        shuffledCombinedArr = np.take_along_axis(combinedArr, randomIndices, axis=1)
        shuffledFile1Arr = shuffledCombinedArr[:,:file1Arr.shape[1]]
        shuffledFile2Arr = shuffledCombinedArr[:,file1Arr.shape[1]:]

        if rowsToCalculate[0] == 0: print("    Time:", time.time() - tShuffle)
        
        return shuffledFile1Arr, shuffledFile2Arr
    else:
        raise ValueError("Could not determine whether score calculation is for real or null data")

# Helper for unflattening a shared array into a 2d numpy array
def sharedToNumpy(sharedArr, numRows, numStates):
    return np.frombuffer(sharedArr.get_obj(), dtype=np.float32).reshape((numRows, numStates))

# initiliazer for multiprocessing
def _init(sharedArr1_, sharedArr2_, totalRows, numStates):
    global sharedArr1
    global sharedArr2
    sharedArr1 = (sharedArr1_, totalRows, numStates)
    sharedArr2 = (sharedArr2_, totalRows, numStates)

# Function that calculates the scores for the S1 metric
def s1Multi(file1Path, file2Path, rowList, totalRows, numStates, expFreqPath, numProcesses, realOrNull):
    print("\nNumber of Processes:", numProcesses)

    sharedArr1 = multiprocessing.Array(np.ctypeslib.as_ctypes_type(np.float32), totalRows * numStates)
    sharedArr2 = multiprocessing.Array(np.ctypeslib.as_ctypes_type(np.float32), totalRows * numStates)

    # Start the processes
    with closing(multiprocessing.Pool(numProcesses, initializer=_init, initargs=(sharedArr1, sharedArr2, totalRows, numStates))) as pool:
        pool.starmap(s1Score, zip(itertools.repeat(file1Path), itertools.repeat(file2Path), rowList, itertools.repeat(expFreqPath), itertools.repeat(realOrNull)))
    pool.join()

    return sharedToNumpy(sharedArr1, totalRows, numStates), sharedToNumpy(sharedArr2, totalRows, numStates)

def s1Score(file1Path, file2Path, rowsToCalculate, expFreqPath, realOrNull):
    file1Arr, file2Arr = readInData(file1Path, file2Path, rowsToCalculate, realOrNull)

    # Loading the expected frequency array
    expFreqArr = np.load(expFreqPath, allow_pickle=False)

    numCols1 = file1Arr.shape[1]
    numCols2 = file2Arr.shape[1]

    scoreArr1 = sharedToNumpy(*sharedArr1)
    scoreArr2 = sharedToNumpy(*sharedArr2)
    
    if rowsToCalculate[0] == 0:
        print("Calculating Scores...")
        tScore = time.time()
        printCheckmarks = [int(rowsToCalculate[1] * float(i / 10)) for i in range(1, 10)]
        percentDone = 0

    # Calculate the observed frequencies and final scores for the designated rows
    for obsRow, scoreRow in enumerate(range(rowsToCalculate[0], rowsToCalculate[1])):

        if rowsToCalculate[0] == 0 and obsRow in printCheckmarks: percentDone += 10; print("    {}% Completed".format(percentDone))

        uniqueStates, stateCounts = np.unique(file1Arr[obsRow], return_counts=True)
        for i, state in enumerate(uniqueStates):
            # Function input is obsFreq and expFreq
            scoreArr1[scoreRow, state] = klScore(stateCounts[i] / numCols1, expFreqArr[state])
        uniqueStates, stateCounts = np.unique(file2Arr[obsRow], return_counts=True)
        for i, state in enumerate(uniqueStates):
            # Function input is obsFreq and expFreq
            scoreArr2[scoreRow, state] = klScore(stateCounts[i] / numCols2, expFreqArr[state])

    if rowsToCalculate[0] == 0: print("    Time:", time.time() - tScore)
        

# Function that calculates the scores for the S2 metric
def s2Multi(file1Path, file2Path, rowList, totalRows, numStates, expFreqPath, numProcesses, realOrNull):
    print("\nNumber of Processes:", numProcesses)

    sharedArr1 = multiprocessing.Array(np.ctypeslib.as_ctypes_type(np.float32), totalRows * numStates)
    sharedArr2 = multiprocessing.Array(np.ctypeslib.as_ctypes_type(np.float32), totalRows * numStates)

    # Start the processes
    with closing(multiprocessing.Pool(numProcesses, initializer=_init, initargs=(sharedArr1, sharedArr2, totalRows, numStates))) as pool:
        pool.starmap(s2Score, zip(itertools.repeat(file1Path), itertools.repeat(file2Path), rowList, itertools.repeat(expFreqPath), itertools.repeat(realOrNull)))
    pool.join()

    return sharedToNumpy(sharedArr1, totalRows, numStates), sharedToNumpy(sharedArr2, totalRows, numStates)


def s2Score(file1Path, file2Path, rowsToCalculate, expFreqPath, realOrNull):
    file1Arr, file2Arr = readInData(file1Path, file2Path, rowsToCalculate, realOrNull)

    # Loading the expected frequency array
    expFreqArr = np.load(expFreqPath, allow_pickle=False)

    numCols = file1Arr.shape[1]
    numStates = sharedArr1[2]

    if rowsToCalculate[0] == 0:
        print("Calculating Scores...")
        tScore = time.time()
        printCheckmarks = [int(rowsToCalculate[1] * float(i / 10)) for i in range(1, 10)]
        percentDone = 0

    # Calculte the scores and store them in the shared array
    scoreArr1 = sharedToNumpy(*sharedArr1)
    scoreArr2 = sharedToNumpy(*sharedArr2)
    # SumOverRows: (Within a row, how many ways can you choose x and y to be together) / (how many ways can you choose 2 states)
    # SumOverRows: (Prob of choosing x and y)
    # Can choose x and y to be together x*y ways if different and n(n-1)/2 ways if same (where n is the number of times that x/y shows up)
    rowObsArr = np.zeros((numStates, numStates))
    permutations = numCols * (numCols - 1)
    for obsRow, scoreRow in enumerate(range(rowsToCalculate[0], rowsToCalculate[1])):

        if rowsToCalculate[0] == 0 and obsRow in printCheckmarks: percentDone += 10; print("    {}% Completed".format(percentDone))

        uniqueStates, stateCounts = np.unique(file1Arr[obsRow], return_counts=True)
        for i, state1 in enumerate(uniqueStates):
            for j, state2 in enumerate(uniqueStates):
                if state1 == state2:
                    rowObsArr[state1, state2] = stateCounts[i] * (stateCounts[i] - 1) / permutations
                else: # state1 > state2 or state1 < state2
                    rowObsArr[state1, state2] = stateCounts[i] * stateCounts[j] / permutations
        # Inputs to klScoreND are obsFreqArr and expFreqArr respectively
        scoreArr1[scoreRow] = klScoreND(rowObsArr, expFreqArr).sum(axis=0)
        # Reset the array so it doesn't carry over values
        rowObsArr.fill(0)
        
        uniqueStates, stateCounts = np.unique(file2Arr[obsRow], return_counts=True)
        for i, state1 in enumerate(uniqueStates):
            for j, state2 in enumerate(uniqueStates):
                if state1 == state2:
                    rowObsArr[state1, state2] = stateCounts[i] * (stateCounts[i] - 1) / permutations
                else: # state1 > state2 or state1 < state2
                    rowObsArr[state1, state2] = stateCounts[i] * stateCounts[j] / permutations
        # Inputs to klScoreND are obsFreqArr and expFreqArr respectively
        scoreArr2[scoreRow] = klScoreND(rowObsArr[obsRow], expFreqArr).sum(axis=0)
        # Reset the array so it doesn't carry over values
        rowObsArr.fill(0)

    if rowsToCalculate[0] == 0: print("    Time:", time.time() - tScore)


# Helper to calculate KL-score (used because math.log2 errors out if obsFreq = 0)
def klScore(obs, exp):
    if obs == 0.0:
        return 0.0
    else:
        return obs * math.log2(obs / exp)


# Helper to calculate KL-score for Nd arrays (cleans up the code)
def klScoreND(obs, exp):
    return obs * ma.log2(ma.divide(obs, exp).filled(0)).filled(0)


# Helper for writing when we are working with real data
def writeReal(diffArr, outputDirPath, fileTag, filename, chrName):
    if not outputDirPath.exists():
        outputDirPath.mkdir(parents=True)

    deltaTxtPath = outputDirPath / "pairwiseDelta_{}_{}.txt.gz".format(fileTag, filename)
    deltaTxt = gzip.open(deltaTxtPath, "wt")

    # Create a location array
    numRows = diffArr.shape[0]
    locationArr = np.array([[chrName, 200*i, 200*i+200] for i in range(numRows)])

    # Creating a string to write out the raw differences (faster than np.savetxt)
    deltaTemplate = "{0[0]}\t{0[1]}\t{0[2]}\t" + "".join("{1[%d]:.5f}\t" % i for i in range(diffArr.shape[1] - 1)) + "{1[%d]:.5f}\n" % (diffArr.shape[1] - 1)
    deltaStr = "".join(deltaTemplate.format(locationArr[i], diffArr[i]) for i in range(diffArr.shape[0]))

    deltaTxt.write(deltaStr)
    deltaTxt.close()


# Helper for writing when we are working with null data
def writeNull(nullDistancesArr, outputDirPath, fileTag, filename, chrName):
    if not outputDirPath.exists():
        outputDirPath.mkdir(parents=True)

    nullDistancesPath = outputDirPath / "temp_nullDistances_{}_{}.npz".format(fileTag, filename)

    np.savez_compressed(nullDistancesPath, chrName=np.array([chrName]), nullDistances=nullDistancesArr)


# Helper for reading number of lines in input file
def blocks(files, size=65536):
    while True:
        b = files.read(size)
        if not b: break
        yield b

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6], sys.argv[7], int(sys.argv[8]), sys.argv[9])