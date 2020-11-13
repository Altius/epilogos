import gzip
import numpy as np
import sys
from pathlib import Path
import math
import pandas as pd
import time
import numpy.ma as ma
import operator as op
from functools import reduce
import itertools
import click

@click.command()
@click.option("-f", "--file-directory", "fileDirectory", type=str, required=True, help="Path to directory that contains files to read from (Please ensure that this directory contains only files you want to read from)")
@click.option("-m", "--state-model", "numStates", type=int, required=True, help="Number of states in chromatin state model")
@click.option("-l", "--saliency-level", "saliency", type=int, required=True, help="Saliency level (1, 2, or 3)")
@click.option("-o", "--output-directory", "outputDirectory", type=str, required=True, help="Output Directory")
@click.option("-e", "--calculate-expected", "calcExp", is_flag=True, help="[Flag] Just calculate the expected frequencies")
@click.option("-s", "--calculate-scores", "calcScores", is_flag=True, help="[Flag] Use previously stored expected frequency array to calculate scores")
@click.option("-d", "--expected-directory", "expFreqDir", type=str, required=True, help="Path to the expected frequency array (Used in conjunction with either '-e' or '-s')")
def main(filename, numStates, saliency, outputDirectory, calcExp, calcScores, expFreqDir):

    if not calcExp and not calcScores:
        print()
        print("ERROR: Please at least one of the --calculate-expected (-e) or --calculate-scores (-s) flags")
        print()
        return

    tTotal = time.time()
    dataFilePath = Path(filename)
    outputDirPath = Path(outputDirectory)

    # Read in the data
    print("\nReading data from file...")
    tRead = time.time()
    dataDF = pd.read_table(dataFilePath, header=None, sep="\t")
    print("    Time: ", time.time() - tRead)

    # Converting to a np array for faster functions later
    print("Converting to numpy array...")
    tConvert = time.time()
    dataArr = dataDF.iloc[:,3:].to_numpy(dtype=int) - 1 
    locationArr = dataDF.iloc[:,0:3].to_numpy(dtype=str)
    print("    Time: ", time.time() - tConvert)

    # Adding the expFreq filename to the path
    expFreqFilename = "exp_freq_" + str(dataArr.shape[1]) + "_" + str(numStates) + "_s" + str(saliency) + ".npy"
    expFreqDir = Path(expFreqDir) / expFreqFilename

    if saliency == 1:
        scoreArr = s1Score(dataDF, dataArr, numStates, outputDirPath, calcExp, calcScores, expFreqDir)
    elif saliency == 2:
        scoreArr =s2Score(dataArr, numStates, outputDirPath, calcExp, calcScores, expFreqDir)
    elif saliency == 3:
        scoreArr = s3Score(dataArr, numStates, outputDirPath, calcExp, calcScores, expFreqDir)
    else:
        print("Inputed saliency value not supported")
        return

    # Only write if there are scores to write
    if calcScores:
        print("Writing to files...")
        tWrite = time.time()
        writeScores(locationArr, scoreArr, outputDirPath, numStates)
        print("    Time: ", time.time() - tWrite)

    print("Total Time: ", time.time() - tTotal)

# Function that calculates the scores for the S1 metric
def s1Score(dataDF, dataArr, numStates, outputDirPath, calcExp, calcScores, expFreqDir):
    numRows, numCols = dataArr.shape

    print("Calculating expected frequencies...")
    tExp = time.time()
    # If user desires, use the stored expected frequency array
    if not calcExp:
        try:
            expFreqArr = np.load(expFreqDir, allow_pickle=False)
        except IOError:
            print("ERROR: Could not load stored expected value array.\n\tPlease check that the directory is correct or that the file exits")
    else:
        # Calculate the expected frequencies of each state
        stateIndices = list(range(1, numStates + 1))
        expFreqSeries = pd.Series(np.zeros(numStates), index=stateIndices)
        dfSize = numRows * numCols
        for i in range(3, numCols + 3):
            stateCounts = dataDF[i].value_counts()
            for state, count in stateCounts.items():
                expFreqSeries.loc[state] += count / dfSize
        expFreqArr = expFreqSeries.to_numpy()

        np.save(expFreqDir, expFreqArr, allow_pickle=False)

    print("    Time: ", time.time() - tExp)

    if calcScores:
        # Calculate the observed frequencies and final scores in one loop
        print("Calculating observed frequencies and scores...")
        tScore = time.time()
        scoreArr = np.zeros((numRows, numStates))
        for row in range(numRows):
            uniqueStates, stateCounts = np.unique(dataArr[row], return_counts=True)
            for i in range(len(uniqueStates)):
                # Function input is obsFreq and expFreq
                scoreArr[row, uniqueStates[i]] = klScore(stateCounts[i] / (numCols), expFreqArr[uniqueStates[i]])
        print("    Time: ", time.time() - tScore)

        return scoreArr

    # return a dummy if we did not calculate scores
    return np.zeros((1,1))

# Function that calculates the scores for the S2 metric
def s2Score(dataArr, numStates, outputDirPath, calcExp, calcScores, expFreqDir):
    numRows, numCols = dataArr.shape

    print("Calculating expected frequencies...")
    tExp = time.time()
    if not calcExp:
        try:
            expFreqArr = np.load(expFreqDir, allow_pickle=False)
        except IOError:
            print("ERROR: Could not load stored expected value array.\n\tPlease check that the directory is correct or that the file exits")
    else:
        obsFreqArr = np.zeros((numRows, numStates, numStates))

        # SumOverRows: (Within a row, how many ways can you choose x and y to be together) / (how many ways can you choose 2 states)
        # SumOverRows: (Prob of choosing x and y)
        # Can choose x and y to be together x*y ways if different and n(n-1)/2 ways if same (where n is the number of times that x/y shows up)
        if sys.version_info < (3, 8):
            print("\nFor maximum efficiency please update python to version 3.8 or later")
            print("NOTE: The code will still run in a lower version, but will be slightly slower\n")
            combinations = ncr(numCols, 2)
            for row in range(numRows):
                uniqueStates, stateCounts = np.unique(dataArr[row], return_counts=True)
                for i in range(len(uniqueStates)):
                    for j in range(len(uniqueStates)):
                        if uniqueStates[i] > uniqueStates[j] or uniqueStates[i] < uniqueStates[j]:
                            obsFreqArr[row, uniqueStates[i], uniqueStates[j]] = stateCounts[i] * stateCounts[j] / combinations / 2 # Extra 2 is to account for the symmetric matrix
                        elif uniqueStates[i] == uniqueStates[j]:
                            obsFreqArr[row, uniqueStates[i], uniqueStates[j]] = ncr(stateCounts[i], 2) / combinations
        else:
            combinations = math.comb(numCols, 2)
            for row in range(numRows):
                uniqueStates, stateCounts = np.unique(dataArr[row], return_counts=True) 
                for i in range(len(uniqueStates)):
                    for j in range(len(uniqueStates)):
                        if uniqueStates[i] > uniqueStates[j] or uniqueStates[i] < uniqueStates[j]:
                            obsFreqArr[row, uniqueStates[i], uniqueStates[j]] = stateCounts[i] * stateCounts[j] / combinations / 2 # Extra 2 is to account for the symmetric matrix
                        elif uniqueStates[i] == uniqueStates[j]:
                            obsFreqArr[row, uniqueStates[i], uniqueStates[j]] = math.comb(stateCounts[i], 2) / combinations

        # Calculate the expected frequencies by summing the observed frequencies for each row
        expFreqArr = obsFreqArr.sum(axis=0) / numRows

        # If the user desires, store the expected frequency array
        np.save(expFreqDir, expFreqArr, allow_pickle=False)

    print("    Time: ", time.time() - tExp)

    if calcScores:
        print("Calculating scores...")
        obsFreqArr = np.zeros((numRows, numStates, numStates))

        # SumOverRows: (Within a row, how many ways can you choose x and y to be together) / (how many ways can you choose 2 states)
        # SumOverRows: (Prob of choosing x and y)
        # Can choose x and y to be together x*y ways if different and n(n-1)/2 ways if same (where n is the number of times that x/y shows up)
        if sys.version_info < (3, 8):
            print("\nFor maximum efficiency please update python to version 3.8 or later")
            print("NOTE: The code will still run in a lower version, but will be slightly slower\n")
            combinations = ncr(numCols, 2)
            for row in range(numRows):
                uniqueStates, stateCounts = np.unique(dataArr[row], return_counts=True)
                for i in range(len(uniqueStates)):
                    for j in range(len(uniqueStates)):
                        if uniqueStates[i] > uniqueStates[j] or uniqueStates[i] < uniqueStates[j]:
                            obsFreqArr[row, uniqueStates[i], uniqueStates[j]] = stateCounts[i] * stateCounts[j] / combinations / 2 # Extra 2 is to account for the symmetric matrix
                        elif uniqueStates[i] == uniqueStates[j]:
                            obsFreqArr[row, uniqueStates[i], uniqueStates[j]] = ncr(stateCounts[i], 2) / combinations
        else:
            combinations = math.comb(numCols, 2)
            for row in range(numRows):
                uniqueStates, stateCounts = np.unique(dataArr[row], return_counts=True) 
                for i in range(len(uniqueStates)):
                    for j in range(len(uniqueStates)):
                        if uniqueStates[i] > uniqueStates[j] or uniqueStates[i] < uniqueStates[j]:
                            obsFreqArr[row, uniqueStates[i], uniqueStates[j]] = stateCounts[i] * stateCounts[j] / combinations / 2 # Extra 2 is to account for the symmetric matrix
                        elif uniqueStates[i] == uniqueStates[j]:
                            obsFreqArr[row, uniqueStates[i], uniqueStates[j]] = math.comb(stateCounts[i], 2) / combinations

        # Calculate the KL Scores
        tScore = time.time()
        scoreArr = np.zeros((numRows, numStates))
        for row in range(numRows):
            scoreArr[row] = klScoreND(obsFreqArr[row], expFreqArr).sum(axis=0)
        print("    Time: ", time.time() - tScore)

        return scoreArr
    
    # return a dummy if we did not calculate scores
    return np.zeros((1,1))

# Function that calculates the scores for the S3 metric
def s3Score(dataArr, numStates, outputDirPath, calcExp, calcScores, expFreqDir):
    numRows, numCols = dataArr.shape

    # FOR TESTING
    rowsToCalculate = range(300)
    # FOR TESTING

    print("Calculating Expected Frequencies...")
    tExp = time.time()
    # If the user desires, use the stored expected frequency array
    if not calcExp:
        try:
            expFreqArr = np.load(expFreqDir, allow_pickle=False)
        except IOError:
            print("ERROR: Could not load stored expected value array.\n\tPlease check that the directory is correct or that the file exits")
    else:
        # Calculate expected frequencies
        expFreqArr = np.zeros((numCols, numCols, numStates, numStates))

        basePermutationArr = np.array(list(itertools.permutations(range(numCols), 2))).T

        # s1 = state 1, s2 = state 2
        for row in rowsToCalculate:
            expFreqArr[basePermutationArr[0], basePermutationArr[1], dataArr[row, basePermutationArr[0]], dataArr[row, basePermutationArr[1]]] += np.ones(basePermutationArr.shape[1])

        # Normalize the array
        expFreqArr /= len(rowsToCalculate) * numCols * (numCols - 1)

        np.save(expFreqDir, expFreqArr, allow_pickle=False)

    print("    Time: ", numRows * (time.time() - tExp) / len(rowsToCalculate))

    if calcScores:
        print("Calculating observed frequencies and scores...")
        tScore = time.time()
        # Because each epigenome, epigenome, state, state combination only occurs once per row, we can precalculate all the scores assuming a frequency of 1/(numCols*(numCols-1))
        # This saves a lot of time in the loop as we are just looking up references and not calculating
        scoreArrOnes = klScoreND(np.ones((numCols, numCols, numStates, numStates)) / (numCols * (numCols - 1)), expFreqArr)

        scoreArr = np.zeros((numRows, numStates))
        for row in rowsToCalculate:
            # Pull the scores from the precalculated score array
            rowScoreArr = np.zeros((numCols, numCols, numStates, numStates))
            rowScoreArr[basePermutationArr[0], basePermutationArr[1], dataArr[row, basePermutationArr[0]], dataArr[row, basePermutationArr[1]]] = scoreArrOnes[basePermutationArr[0], basePermutationArr[1], dataArr[row, basePermutationArr[0]], dataArr[row, basePermutationArr[1]]]

            scoreArr[row] = rowScoreArr.sum(axis=(0,1,2))

        print("    Time: ", numRows * (time.time() - tScore) / len(rowsToCalculate))

        return scoreArr

    # return a dummy if we did not calculate scores
    return np.zeros((1,1))

# Helper to calculate KL-score (used because math.log2 errors out if obsFreq = 0)
def klScore(obs, exp):
    if obs == 0.0:
        return 0.0
    else:
        return obs * math.log2(obs / exp)

# Helper to calculate KL-score for 2d arrays (cleans up the code)
def klScoreND(obs, exp):
    return obs * ma.log2(ma.divide(obs, exp).filled(0)).filled(0)

# Helper to write the final scores to files
def writeScores(locationArr, scoreArr, outputDirPath, numStates):
    if not outputDirPath.exists():
        outputDirPath.mkdir(parents=True)

    observationsTxtPath = outputDirPath / "observationsV.txt.gz"
    scoresTxtPath = outputDirPath / "scoresV.txt.gz"

    observationsTxt = gzip.open(observationsTxtPath, "wt")
    scoresTxt = gzip.open(scoresTxtPath, "wt")

    # Write each row in both observations and scores
    for i in range(locationArr.shape[0]):
        # Write in the coordinates
        for location in locationArr[i]:
            observationsTxt.write("{}\t".format(location))
            scoresTxt.write("{}\t".format(location))
        
        # Write to observations
        maxContribution = np.amax(scoreArr[i])
        maxContributionLoc = np.argmax(scoreArr[i]) + 1
        totalScore = np.sum(scoreArr[i])

        observationsTxt.write("{}\t{:.5f}\t1\t{:.5f}\t\n".format(maxContributionLoc, maxContribution, totalScore))

        # Write to scores
        for j in range(scoreArr.shape[1]):
            scoresTxt.write("{0:.5f}\t".format(scoreArr[i, j]))
        scoresTxt.write("\n")

    observationsTxt.close()
    scoresTxt.close()

# Helper to calculate combinations
def ncr(n, r):
    r = min(r, n-r)
    numer = reduce(op.mul, range(n, n - r, -1), 1)
    denom = reduce(op.mul, range(1, r + 1), 1)
    return numer // denom

if __name__ == "__main__":
    main()