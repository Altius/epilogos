from sys import argv
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd
import scipy.stats as st
import warnings
from time import time
import gzip
from multiprocessing import cpu_count, Pool
from contextlib import closing
from itertools import repeat
from os import remove

def main(group1Name, group2Name, numStates, outputDir, fileTag, numProcesses, diagnosticBool, numTrials, samplingSize):
    tTotal = time()

    outputDirPath = Path(outputDir)
    np.random.seed(7032016)


    # Plotting setting
    plt.rcParams['agg.path.chunksize'] = 10000
    
    if numStates == 18:
        stateColorList = np.array([(1.0, 0.0, 0.0), (1.0, 0.2706, 0.0), (1.0, 0.2706, 0.0), (1.0, 0.2706, 0.0), (0.0, 0.502, 0.0), (0.0, 0.3922, 0.0), (0.7608, 0.8824, 0.0196), (0.7608, 0.8824, 0.0196), (1.0, 0.7647, 0.302), (1.0, 0.7647, 0.302), (1.0, 1.0, 0.0), (0.4, 0.8039, 0.6667), (0.5412, 0.5686, 0.8157), (0.8039, 0.3608, 0.3608), (0.7412, 0.7176, 0.4196), (0.502, 0.502, 0.502), (0.7529, 0.7529, 0.7529), (1.0, 1.0, 1.0)])
        stateNameList = np.array(["TssA", "TssFlnk", "TssFlnkU", "TssFlnkD", "Tx", "TxWk", "EnhG1", "EnhG2", "EnhA1", "EnhA2", "EnhWk", "ZNF/Rpts", "Het", "TssBiv", "EnhBiv", "ReprPC", "ReprPCWk", "Quies"])
    elif numStates == 15:
        stateColorList = np.array([(1.0, 0.0, 0.0), (1.0, 0.27059, 0.0), (0.19608, 0.80392, 0.19608), (0.0, 0.50196, 0.0), (0.0, 0.39216, 0.0), (0.76078, 0.88235, 0.01961), (1.0, 1.0, 0.0), (0.4, 0.80392, 0.66667), (0.54118, 0.56863, 0.81569), (0.80392, 0.36078, 0.36078), (0.91373, 0.58824, 0.47843), (0.74118, 0.71765, 0.41961), (0.50196, 0.50196, 0.50196), (0.75294, 0.75294, 0.75294), (1.0, 1.0, 1.0)])
        stateNameList = np.array(["TssA", "TssAFlnk", "TxFlnk", "Tx", "TxWk", "EnhG", "Enh", "ZNF/Rpts", "Het", "TssBiv", "BivFlnk", "EnhBiv", "ReprPC", "ReprPCWk", "Quies"])
    else:
        raise ValueError("State model not supported for plotting")

    # If user doesn't want to choose number of cores use as many as available
    if numProcesses == 0:
        numProcesses = cpu_count()

    # Read in observation files
    print("\nReading in observation files...", flush=True)
    tRead = time()
    locationArr, distanceArrReal, distanceArrNull, maxDiffArr, diffArr = readInData(outputDirPath, numProcesses, numStates)
    print("    Time:", time() - tRead, flush=True)

    print("Unique Distances:", len(np.unique(distanceArrReal)))

    # Fitting a gennorm distribution to the distances
    print("Fitting gennorm distribution to distances...", flush=True)
    tFit = time()
    params, dataReal, dataNull = fitDistances(distanceArrReal, distanceArrNull, diffArr, numStates, numProcesses, outputDirPath, numTrials, samplingSize)
    # fitDistances(distanceArrReal, distanceArrNull, diffArr, numStates, numProcesses, outputDirPath, numTrials, samplingSize)
    print("    Time:", time() - tFit, flush=True)

    # Splitting the params up
    beta, loc, scale = params[:-2], params[-2], params[-1]
    print("PARAMS: ", params)

    # Creating Diagnostic Figures
    if diagnosticBool:
        print("Creating diagnostic figures...")
        tDiagnostic = time()
        createDiagnosticFigures(dataReal, dataNull, distanceArrReal, distanceArrNull, beta, loc, scale, outputDirPath, fileTag)
        print("    Time:", time() - tDiagnostic)

    # Calculating PValues
    print("Calculating P-Values...")
    tPVal = time()
    pvals = calculatePVals(distanceArrReal, beta, loc, scale)
    print("    Time:", time() - tPVal)

    # Create an output file which summarizes the results
    print("Writing metrics file...")
    tMetrics = time()
    writeMetrics(locationArr, maxDiffArr, distanceArrReal, pvals, outputDirPath, fileTag)
    print("    Time:", time() - tMetrics)

    # # Create txt file of top 1000 loci with adjacent merged
    # print("Creating .txt file of top loci...")
    # t1000 = time()
    # roiPath = outputDirPath / "greatestHits_{}.txt".format(fileTag)
    # sendRoiUrl(roiPath, locationArr, distanceArrReal, maxDiffArr, stateNameList, pvals, -1)
    # print("    Time:", time() - t1000)

    # # Determine Significance Threshold (based on n*)
    # genomeAutoCorrelation = 0.987
    # nStar = len(distanceArrReal) * ((1 - genomeAutoCorrelation) / (1 + genomeAutoCorrelation))
    # significanceThreshold = .1 / nStar

    # # Create txt file of significant loci
    # print("Creating .txt file of significant loci...")
    # tSig = time()
    # roiPath = outputDirPath / "signficantLoci_{}.txt".format(fileTag)
    # sendRoiUrl(roiPath, locationArr, distanceArrReal, maxDiffArr, stateNameList, pvals, significanceThreshold)
    # print("    Time:", time() - tSig)

    # # Create Genome Manhattan Plot
    # print("Creating Genome-Wide Manhattan Plot")
    # tGManhattan = time()
    # createGenomeManhattan(group1Name, group2Name, locationArr, distanceArrReal, maxDiffArr, beta, loc, scale, significanceThreshold, pvals, stateColorList, outputDirPath, fileTag)
    # print("    Time:", time() - tGManhattan)
    
    # # Create Chromosome Manhattan Plot
    # print("Creating Individual Chromosome Manhattan Plots")
    # tCManhattan = time()
    # createChromosomeManhattan(group1Name, group2Name, locationArr, distanceArrReal, maxDiffArr, beta, loc, scale, significanceThreshold, pvals, stateColorList, outputDirPath, fileTag, numProcesses)
    # print("    Time:", time() - tCManhattan)

    print("Total Time:", time() - tTotal, flush=True)

# Helper to read in the necessary data to fit and visualize pairwise results
def readInData(outputDirPath, numProcesses, numStates):
    # For keeping the data arrays organized correctly
    realNames = ["chr", "binStart", "binEnd"] + ["s{}".format(i) for i in range(1, numStates + 1)]
    # chrOrder = ["chr{}".format(i) for i in range(1, 23)] + ["chrX"]

    # Data frame to dump inputed data into
    diffDF = pd.DataFrame(columns=realNames)
    
    # Multiprocess the reading
    with closing(Pool(numProcesses)) as pool:
        results = pool.starmap(readTableMulti, zip(outputDirPath.glob("pairwiseDelta_*.txt.gz"), outputDirPath.glob("temp_nullDistances_*.npz"), repeat(realNames)))
    pool.join()

    # Concatenating all chunks to the real differences dataframe
    for diffDFChunk, _ in results:
        diffDF = pd.concat((diffDF, diffDFChunk), axis=0, ignore_index=True)

    # Figuring out chromosome order
    chromosomes = diffDF.loc[diffDF['binStart'] == 0]['chr'].values
    rawChrNamesInts = []
    rawChrNamesStrs = []

    for chr in chromosomes:
        try:
            rawChrNamesInts.append(int(chr.split("chr")[-1]))
        except ValueError:
            rawChrNamesStrs.append(chr.split("chr")[-1])

    rawChrNamesInts.sort()
    rawChrNamesStrs.sort()

    chrOrder = rawChrNamesInts + rawChrNamesStrs

    for i in range(len(chrOrder)):
        chrOrder[i] = "chr" + str(chrOrder[i])

    # Sorting the dataframes by chromosomal location
    diffDF["chr"] = pd.Categorical(diffDF["chr"], categories=chrOrder, ordered=True)
    diffDF.sort_values(by=["chr", "binStart", "binEnd"], inplace=True)

    # Convert dataframes to np arrays for easier manipulation
    locationArr     = diffDF.iloc[:,0:3].to_numpy(dtype=str)
    diffArr         = diffDF.iloc[:,3:].to_numpy(dtype=float)

    # Creating array of null distances ordered by chromosome based on the read in chunks
    nullChunks = list(zip(*list(zip(*results))[1]))
    index = nullChunks[0].index(chrOrder[0])
    distanceArrNull = nullChunks[1][index]
    for chrName in chrOrder[1:]:
        index = nullChunks[0].index(chrName)
        distanceArrNull = np.concatenate((distanceArrNull, nullChunks[1][index]))

    # Cleaning up the temp files after we've read them
    for file in outputDirPath.glob("temp_nullDistances_*.npz"):
        remove(file)

    # Calculate the distance array for the real data
    diffSign = np.sign(np.sum(diffArr, axis=1))
    distanceArrReal = np.sum(np.square(diffArr), axis=1) * diffSign

    # Calculate the maximum contributing state for each bin
    # In the case of a tie, the higher number state wins (e.g. last state wins if all states are 0)
    maxDiffArr = np.abs(np.argmax(np.abs(np.flip(diffArr, axis=1)), axis=1) - diffArr.shape[1]).astype(int)

    return locationArr, distanceArrReal, distanceArrNull, maxDiffArr, diffArr

def readTableMulti(realFile, nullFile, realNames):
    diffDFChunk = pd.read_table(Path(realFile), header=None, sep="\t", names=realNames)
    npzFile = np.load(Path(nullFile))

    return diffDFChunk, (npzFile['chrName'][0], npzFile['nullDistances'])

# # Helper to fit the distances
# def fitDistances(distanceArrReal, distanceArrNull, diffArr, numStates, numProcesses, outputDirPath, numTrials, samplingSize):
#     # Filtering out quiescent values (When there are exactly zero differences between both score arrays)
#     idx = [i for i in range(len(distanceArrReal)) if round(distanceArrReal[i], 5) != 0 or np.any(diffArr[i] != np.zeros((numStates)))]
#     dataReal = pd.Series(distanceArrReal[idx])
#     dataNull = pd.Series(distanceArrNull[idx])

#     # ignore warnings
#     with warnings.catch_warnings():
#         warnings.simplefilter("ignore")

#         # Fit the data
#         params = st.gennorm.fit(dataNull)
#         mle = st.gennorm.nnlf(params, pd.Series(dataNull))

#         print("MLE:", mle)

#     return params, dataReal, dataNull

# Helper to fit the distances
def fitDistances(distanceArrReal, distanceArrNull, diffArr, numStates, numProcesses, outputDir, numTrials, samplingSize):
    # Filtering out quiescent values (When there are exactly zero differences between both score arrays)
    idx = [i for i in range(len(distanceArrReal)) if round(distanceArrReal[i], 5) != 0 or np.any(diffArr[i] != np.zeros((numStates)))]
    dataReal = pd.Series(distanceArrReal[idx])
    dataNull = pd.Series(distanceArrNull[idx])

    # numTrials = 1000

    with closing(Pool(numProcesses)) as pool:
        results = pool.starmap(fitOnBootstrap, zip(repeat(distanceArrNull[idx], numTrials), repeat(samplingSize, numTrials)))
    pool.join()

    with open(outputDir / "fitResults.txt", 'w') as f:
        index = [i for i in range(numTrials)]
        columns = ["beta", "loc", "scale", "mle"]

        fitDF = pd.DataFrame(index=index, columns=columns)

        for i in range(len(results)):
            beta  = results[i][0][0]
            loc   = results[i][0][1]
            scale = results[i][0][2]
            mle   = results[i][1]

            f.write("{}\t{}\t{}\t{}\n".format(beta, loc, scale, mle))
            fitDF.iloc[i, 0] = results[i][0][0]
            fitDF.iloc[i, 1] = results[i][0][1]
            fitDF.iloc[i, 2] = results[i][0][2]
            fitDF.iloc[i, 3] = results[i][1]

        fitDF.sort_values(by=["mle"], inplace=True)

    # params = tuple(map(lambda x: x/len(results), tuple(map(sum, zip(*results)))))

    # return params, dataReal, dataNull
    medianIndex = int((numTrials-1)/2)
    return (fitDF.iloc[medianIndex, 0], fitDF.iloc[medianIndex, 1], fitDF.iloc[medianIndex, 2]), dataReal, dataNull
    # return (beta, loc, scale), dataReal, dataNull


def fitOnBootstrap(distanceArrNull, samplingSize):
    # samplingSize = 10000
    if len(distanceArrNull) <= samplingSize:
        bootstrapData = distanceArrNull
    else:
        np.random.seed()
        bootstrapData = pd.Series(np.random.choice(distanceArrNull, size=samplingSize, replace=False))

    # ignore warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        # Fit the data
        params = st.gennorm.fit(bootstrapData)

        # Calculate SSE and MLE
        mle = st.gennorm.nnlf(params, pd.Series(distanceArrNull))

    return params, mle


# Helper for creating and saving diagnostic figures
def createDiagnosticFigures(dataReal, dataNull, distanceArrReal, distanceArrNull, beta, loc, scale, outputDirPath, fileTag):
    diagnosticDirPath = outputDirPath / "diagnosticFigures_{}".format(fileTag)
    if not diagnosticDirPath.exists():
        diagnosticDirPath.mkdir(parents=True)
    
    # Real Data Histogram vs. Null Data Histogram (Range=(-1, 1))
    fig = plt.figure(figsize=(16,9))
    ax = fig.add_subplot(111)
    dataReal.plot(kind='hist', bins=200, range=(-1, 1), density=True, alpha=0.5, label='Non-Random Distances', legend=True, ax=ax)
    dataNull.plot(kind='hist', bins=200, range=(-1, 1), density=True, alpha=0.5, label='Random Distances', legend=True, ax=ax)
    plt.title("Real Data vs. Null Data (range=(-1, 1))")
    figPath = diagnosticDirPath / "real_vs_null_histogram_n1to1.png"
    fig.savefig(figPath, bbox_inches='tight', dpi=300, facecolor="#FFFFFF", edgecolor="#FFFFFF", transparent=False)
    plt.close(fig)

    # Real Data Histogram vs. Null Data Histogram (Range=(-max(abs), max(abs)))
    fig = plt.figure(figsize=(16,9))
    ax = fig.add_subplot(111)
    rangeLim = np.amax(np.abs(dataReal))
    dataReal.plot(kind='hist', bins=200, range=(-rangeLim, rangeLim), density=True, alpha=0.5, label='Non-Random Distances', legend=True, ax=ax)
    dataNull.plot(kind='hist', bins=200, range=(-rangeLim, rangeLim), density=True, alpha=0.5, label='Random Distances', legend=True, ax=ax)
    plt.title("Real Data vs. Null Data (range=(-max(abs), max(abs)))")
    figPath = diagnosticDirPath / "real_vs_null_histogram_minToMax.png"
    fig.savefig(figPath, bbox_inches='tight', dpi=300, facecolor="#FFFFFF", edgecolor="#FFFFFF", transparent=False)
    plt.close(fig)

    # Real vs Null distance scatter plot
    fig = plt.figure(figsize=(12,12))
    plt.scatter(distanceArrReal, distanceArrNull, color='r')
    plt.xlim(-rangeLim, rangeLim)
    plt.ylim(-rangeLim, rangeLim)
    plt.xlabel("Real Distances")
    plt.ylabel("Null Distances")
    plt.title("Real Distances vs Null Distances")
    figPath = diagnosticDirPath / "real_vs_null_scatter.png"
    fig.savefig(figPath, bbox_inches='tight', dpi=300, facecolor="#FFFFFF", edgecolor="#FFFFFF", transparent=False)
    plt.close(fig)

    # Fit on data (range=(min, max))
    y, x = np.histogram(dataNull, bins=20000, range=(np.amin(distanceArrNull), np.amax(distanceArrNull)), density=True);
    x = (x + np.roll(x, -1))[:-1] / 2.0
    fig = plt.figure(figsize=(12,8))
    pdf = st.gennorm.pdf(x, beta, loc=loc, scale=scale)
    ax = pd.Series(pdf, x).plot(label='gennorm(beta={}, loc={}, scale={})'.format(beta,loc,scale), legend=True)
    dataNull.plot(kind='hist', bins=20000, range=(np.amin(distanceArrNull), np.amax(distanceArrNull)), density=True, alpha=0.5, label='Data', legend=True, ax=ax)
    plt.title("Gennorm on data (range=(min,max))")
    plt.xlabel("Signed Squared Euclidean Distance")
    figPath = diagnosticDirPath / "gennorm_on_data_minToMax.png"
    fig.savefig(figPath, bbox_inches='tight', dpi=300, facecolor="#FFFFFF", edgecolor="#FFFFFF", transparent=False)
    plt.close(fig)

    # Fit on data (range=(-1, 1))
    y, x = np.histogram(dataNull, bins=20000, range=(-1, 1), density=True);
    x = (x + np.roll(x, -1))[:-1] / 2.0
    fig = plt.figure(figsize=(12,8))
    pdf = st.gennorm.pdf(x, beta, loc=loc, scale=scale)
    ax = pd.Series(pdf, x).plot(label='gennorm(beta={}, loc={}, scale={})'.format(beta,loc,scale), legend=True)
    dataNull.plot(kind='hist', bins=20000, range=(-1, 1), density=True, alpha=0.5, label='Data', legend=True, ax=ax)
    plt.title("Gennorm on data (range=(-1,1))")
    plt.xlabel("Signed Squared Euclidean Distance")
    figPath = diagnosticDirPath / "gennorm_on_data_n1to1.png"
    fig.savefig(figPath, bbox_inches='tight', dpi=300, facecolor="#FFFFFF", edgecolor="#FFFFFF", transparent=False)
    plt.close(fig)

    # Fit on data (range=(-0.1, 0.1))
    y, x = np.histogram(dataNull, bins=20000, range=(-1, 1), density=True);
    x = (x + np.roll(x, -1))[:-1] / 2.0
    fig = plt.figure(figsize=(12,8))
    pdf = st.gennorm.pdf(x, beta, loc=loc, scale=scale)
    ax = pd.Series(pdf, x).plot(label='gennorm(beta={}, loc={}, scale={})'.format(beta,loc,scale), legend=True)
    dataNull.plot(kind='hist', bins=20000, range=(-1, 1), density=True, alpha=0.5, label='Data', legend=True, ax=ax)
    plt.title("Gennorm on data (range=(-0.1,0.1))")
    plt.xlim(-.1, .1)
    plt.xlabel("Signed Squared Euclidean Distance")
    figPath = diagnosticDirPath / "gennorm_on_data_0p1to0p1.png"
    fig.savefig(figPath, bbox_inches='tight', dpi=300, facecolor="#FFFFFF", edgecolor="#FFFFFF", transparent=False)
    plt.close(fig)


# Helper to find the P-Values of all the distances
def calculatePVals(distanceArrReal, beta, loc, scale):
    pvalsBelowLoc = 2 * st.gennorm.cdf(distanceArrReal[np.where(distanceArrReal <= loc)[0]], beta, loc=loc, scale=scale)
    pvalsAboveLoc = 2 * (1 - st.gennorm.cdf(distanceArrReal[np.where(distanceArrReal > loc)[0]], beta, loc=loc, scale=scale))
    
    pvals = np.zeros(len(distanceArrReal))
    pvals[np.where(distanceArrReal <= loc)[0]] = pvalsBelowLoc
    pvals[np.where(distanceArrReal > loc)[0]]  = pvalsAboveLoc

    return pvals


# Helper to create a genome-wide manhattan plot
def createGenomeManhattan(group1Name, group2Name, locationArr, distanceArrReal, maxDiffArr, beta, loc, scale, significanceThreshold, pvals, stateColorList, outputDirPath, fileTag):
    manhattanDirPath = outputDirPath / "manhattanPlots_{}".format(fileTag)
    if not manhattanDirPath.exists():
        manhattanDirPath.mkdir(parents=True)

    logSignificanceThreshold = -np.log10(significanceThreshold)

    fig = plt.figure(figsize=(16,9))
    ax = fig.add_subplot(111)
    ax.set_facecolor("#FFFFFF")
    ax.set_axisbelow(True)
    ax.grid(True, axis='both', color='k', linewidth=.25, linestyle="-")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    plt.title("Differential epilogos between {} and {} biosamples".format(group1Name, group2Name))
    ax.set_ylabel("Distance")
    plt.xlabel("Chromosome")
    xticks = np.where(locationArr[:, 1] == "0")[0]
    plt.xticks(ticks=xticks, labels=list(map(lambda x: x.split("chr")[-1], list(locationArr[:, 0][xticks]))))

    plt.margins(x=0)
    ylim = np.amax(np.abs(distanceArrReal)) * 1.1
    ax.set_ylim(-ylim, ylim)
    yticks, ytickLabels = pvalAxisScaling(ylim, beta, loc, scale)

    ax.set_yticks(yticks)
    ax.set_yticklabels([str(np.abs(np.round(val, 1))) for val in yticks])

    axR = ax.twinx()
    axR.set_ylabel("P-Value")
    axR.spines["top"].set_visible(False)
    axR.spines["left"].set_visible(False)
    axR.spines["bottom"].set_visible(False)
    axR.set_yticks(yticks)
    axR.set_ylim(ax.get_ylim())
    axR.set_yticklabels(ytickLabels)

    ax.text(0.99, 0.99, group1Name, verticalalignment='top', horizontalalignment='right', transform=ax.transAxes, fontsize=15)
    ax.text(0.99, 0.01, group2Name, verticalalignment='bottom', horizontalalignment='right', transform=ax.transAxes, fontsize=15)

    locationOnGenome = np.arange(len(distanceArrReal))
    pvalsGraph = -np.log10(pvals.astype(float)) * np.sign(distanceArrReal)

    for i in range(len(xticks)):
        if i == len(xticks)-1:
            points = np.where((locationOnGenome >= xticks[i]) & (np.abs(pvalsGraph) < logSignificanceThreshold))[0]
            plt.scatter(locationOnGenome[points], distanceArrReal[points], s=(np.abs(distanceArrReal[points]) / np.amax(np.abs(distanceArrReal)) * 100), color="gray", marker=".", alpha=0.1, edgecolors='none', rasterize=True)
        elif i%2 == 0:
            points = np.where((locationOnGenome >= xticks[i]) & (locationOnGenome < xticks[i+1]) & (np.abs(pvalsGraph) < logSignificanceThreshold))[0]
            plt.scatter(locationOnGenome[points], distanceArrReal[points], s=(np.abs(distanceArrReal[points]) / np.amax(np.abs(distanceArrReal)) * 100), color="gray", marker=".", alpha=0.1, edgecolors='none', rasterize=True)
        else:
            points = np.where((locationOnGenome >= xticks[i]) & (locationOnGenome < xticks[i+1]) & (np.abs(pvalsGraph) < logSignificanceThreshold))[0]
            plt.scatter(locationOnGenome[points], distanceArrReal[points], s=(np.abs(distanceArrReal[points]) / np.amax(np.abs(distanceArrReal)) * 100), color="black", marker=".", alpha=0.1, edgecolors='none', rasterize=True)
            
    opaqueSigIndices = np.where(np.abs(pvalsGraph) >= logSignificanceThreshold)[0]

    colorArr=np.array(stateColorList)[maxDiffArr[opaqueSigIndices].astype(int) - 1]
    opacityArr=np.array((np.abs(distanceArrReal[opaqueSigIndices]) / np.amax(np.abs(distanceArrReal)))).reshape(len(distanceArrReal[opaqueSigIndices]), 1)
    rgbaColorArr = np.concatenate((colorArr, opacityArr), axis=1)
    sizeArr = np.abs(distanceArrReal[opaqueSigIndices]) / np.amax(np.abs(distanceArrReal)) * 100

    plt.scatter(opaqueSigIndices, distanceArrReal[opaqueSigIndices], s=sizeArr, color=rgbaColorArr, marker=".", edgecolors='none', rasterize=True)
    ax.axhline(st.gennorm.isf(significanceThreshold/2, beta, loc=loc, scale=scale), linewidth=.25, linestyle="-")
    ax.axhline(-st.gennorm.isf(significanceThreshold/2, beta, loc=loc, scale=scale), linewidth=.25, linestyle="-")

    figPath = manhattanDirPath / "manhattan_plot_genome.pdf"
    fig.savefig(figPath, bbox_inches='tight', dpi=400, facecolor="#FFFFFF", edgecolor="#FFFFFF", transparent=False)
    plt.close(fig)


# Helper for generating individual chromosome manhattan plots
def createChromosomeManhattan(group1Name, group2Name, locationArr, distanceArrReal, maxDiffArr, beta, loc, scale, significanceThreshold, pvals, stateColorList, outputDirPath, fileTag, numProcesses):
    manhattanDirPath = outputDirPath / "manhattanPlots_{}".format(fileTag)
    if not manhattanDirPath.exists():
        manhattanDirPath.mkdir(parents=True)

    pvalsGraph = -np.log10(pvals.astype(float)) * np.sign(distanceArrReal)

    txticks = time()
    xticks = np.where(locationArr[:, 1] == "0")[0]
    startEnd = []
    for i in range(len(xticks)):
        if not i == len(xticks) - 1:
            startEnd.append((xticks[i], xticks[i+1]))
        else:
            startEnd.append((xticks[i], -1))
    print("Time to create startEnd:", time() - txticks)

    tChrOrder = time()
    chrOrder = list(map(lambda x: x.split("chr")[-1], list(locationArr[:, 0][xticks])))
    print("Time to determine chrOrder:", time() - tChrOrder)

    tChromosome = time()
    # Multiprocess the reading
    with closing(Pool(numProcesses)) as pool:
        pool.starmap(graphChromosomeManhattan, zip(chrOrder, startEnd, repeat(group1Name), repeat(group2Name), repeat(locationArr), repeat(distanceArrReal), repeat(maxDiffArr), repeat(beta), repeat(loc), repeat(scale), repeat(significanceThreshold), repeat(pvalsGraph), repeat(stateColorList), repeat(manhattanDirPath)))
    pool.join()
    print("Time for chromosome manhattan:", time() - tChromosome)


def graphChromosomeManhattan(chromosome, startEnd, group1Name, group2Name, locationArr, distanceArrReal, maxDiffArr, beta, loc, scale, significanceThreshold, pvalsGraph, stateColorList, manhattanDirPath):
    logSignificanceThreshold = -np.log10(significanceThreshold)    

    fig = plt.figure(figsize=(16,9))
    ax = fig.add_subplot(111)
    ax.set_facecolor("#FFFFFF")
    ax.set_axisbelow(True)
    ax.grid(True, axis='y', color='k', linewidth=.25, linestyle="-")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.set_ylabel("Distance")
    plt.xlabel("Location in Chromosome {} (Mb)".format(chromosome))
    plt.title("Differential epilogos between {} and {} donor biosamples (Chromosome {})".format(group1Name, group2Name, chromosome))

    plt.margins(x=0)
    ylim = np.amax(np.abs(distanceArrReal)) * 1.1
    ax.set_ylim(-ylim, ylim)
    yticks, ytickLabels = pvalAxisScaling(ylim, beta, loc, scale)

    ax.set_yticks(yticks)
    ax.set_yticklabels([str(np.abs(np.round(val, 1))) for val in yticks])

    axR = ax.twinx()
    axR.set_ylabel("P-Value")
    axR.spines["top"].set_visible(False)
    axR.spines["left"].set_visible(False)
    axR.spines["bottom"].set_visible(False)
    axR.set_yticks(yticks)
    axR.set_ylim(ax.get_ylim())
    axR.set_yticklabels(ytickLabels)

    ax.text(0.99, 0.99, group1Name, verticalalignment='top', horizontalalignment='right', transform=ax.transAxes, fontsize=15)
    ax.text(0.99, 0.01, group2Name, verticalalignment='bottom', horizontalalignment='right', transform=ax.transAxes, fontsize=15)

    locationOnGenome = np.arange(len(distanceArrReal))

    if startEnd[1] == -1:
        realxticks = np.where((locationOnGenome >= startEnd[0]) & (locationArr[:, 1].astype(int)%10000000 == 0))[0]
        plt.xticks(ticks=realxticks, labels=[str(int(int(locationArr[tick, 1])/1000000)) for tick in realxticks])

        points = np.where((locationOnGenome >= startEnd[0]) & (np.abs(pvalsGraph) < logSignificanceThreshold))[0]
        plt.scatter(locationOnGenome[points], distanceArrReal[points], s=(np.abs(distanceArrReal[points]) / np.amax(np.abs(distanceArrReal)) * 100), color="gray", marker=".", alpha=0.1, edgecolors='none', rasterize=True)

        opaqueSigIndices = np.where((locationOnGenome >= startEnd[0]) & (np.abs(pvalsGraph) >= logSignificanceThreshold))[0]
    else:
        realxticks = np.where(((locationOnGenome >= startEnd[0]) & (locationOnGenome < startEnd[1])) & (locationArr[:, 1].astype(int)%10000000 == 0))[0]
        plt.xticks(ticks=realxticks, labels=[str(int(int(locationArr[tick, 1])/1000000)) for tick in realxticks])

        points = np.where(((locationOnGenome >= startEnd[0]) & (locationOnGenome < startEnd[1])) & (np.abs(pvalsGraph) < logSignificanceThreshold))[0]
        plt.scatter(locationOnGenome[points], distanceArrReal[points], s=(np.abs(distanceArrReal[points]) / np.amax(np.abs(distanceArrReal)) * 100), color="gray", marker=".", alpha=0.1, edgecolors='none', rasterize=True)

        opaqueSigIndices = np.where(((locationOnGenome >= startEnd[0]) & (locationOnGenome < startEnd[1])) & (np.abs(pvalsGraph) >= logSignificanceThreshold))[0]

    colorArr=np.array(stateColorList)[maxDiffArr[opaqueSigIndices].astype(int) - 1]
    opacityArr=np.array((np.abs(distanceArrReal[opaqueSigIndices]) / np.amax(np.abs(distanceArrReal)))).reshape(len(distanceArrReal[opaqueSigIndices]), 1)
    rgbaColorArr = np.concatenate((colorArr, opacityArr), axis=1)
    sizeArr = np.abs(distanceArrReal[opaqueSigIndices]) / np.amax(np.abs(distanceArrReal)) * 100

    plt.scatter(opaqueSigIndices, distanceArrReal[opaqueSigIndices], s=sizeArr, color=rgbaColorArr, marker=".", edgecolors='none', rasterize=True)
    ax.axhline(st.gennorm.isf(significanceThreshold/2, beta, loc=loc, scale=scale), linewidth=.25, linestyle="-")
    ax.axhline(-st.gennorm.isf(significanceThreshold/2, beta, loc=loc, scale=scale), linewidth=.25, linestyle="-")
    
    figPath = manhattanDirPath / "manhattan_plot_chr{}.pdf".format(chromosome)
    fig.savefig(figPath, bbox_inches='tight', dpi=400, facecolor="#FFFFFF", edgecolor="#FFFFFF", transparent=False)
    plt.close(fig)

# Helper function for generating proper tick marks on the manhattan plots
def pvalAxisScaling(ylim, beta, loc, scale):
    yticks = []
    ytickLabels = ["$10^{-16}$", "$10^{-15}$", "$10^{-14}$", "$10^{-13}$", "$10^{-12}$", "$10^{-11}$", "$10^{-10}$", "$10^{-9}$", "$10^{-8}$", "$10^{-7}$", "$10^{-6}$", "$10^{-5}$", "$10^{-4}$", "$1$", "$10^{-4}$", "$10^{-5}$", "$10^{-6}$", "$10^{-7}$", "$10^{-8}$", "$10^{-9}$", "$10^{-10}$", "$10^{-11}$", "$10^{-12}$", "$10^{-13}$", "$10^{-14}$", "$10^{-15}$", "$10^{-16}$"]

    for i in range(-16, -3):
        yticks.append(-st.gennorm.isf(10**i/2, beta, loc=loc, scale=scale))
        yticks.append(st.gennorm.isf(10**i/2, beta, loc=loc, scale=scale))
    yticks.append(0)
    yticks.sort()

    yticksFinal = []
    ytickLabelsFinal = []
    
    for i in range(len(yticks)):
        if yticks[i] >= -ylim and yticks[i] <= ylim:
            yticksFinal.append(float(yticks[i]))
            ytickLabelsFinal.append(ytickLabels[i])
            
    return (yticksFinal, ytickLabelsFinal)
    

# Helper to write the metrics file to disk
def writeMetrics(locationArr, maxDiffArr, distanceArrReal, pvals, outputDirPath, fileTag):
    if not outputDirPath.exists():
        outputDirPath.mkdir(parents=True)

    metricsTxtPath = outputDirPath / "pairwiseMetrics_{}.txt.gz".format(fileTag)
    metricsTxt = gzip.open(metricsTxtPath, "wt")

    # Creating a string to write out the raw differences (faster than np.savetxt)
    metricsTemplate = "{0[0]}\t{0[1]}\t{0[2]}\t{1}\t{2:.5f}\t{3:.5e}\n"
    metricsStr = "".join(metricsTemplate.format(locationArr[i], maxDiffArr[i], distanceArrReal[i], pvals[i]) for i in range(len(distanceArrReal)))

    metricsTxt.write(metricsStr)
    metricsTxt.close()


# Helper function to create a roiURL txt file of the top 1000 loci (Adjacent loci are merged)
def sendRoiUrl(filePath, locationArr, distanceArr, maxDiffArr, nameArr, pvals, significanceThreshold):
    with open(filePath, 'w') as f:
        if significanceThreshold < 0:
            # Sort the values
            indices = (-np.abs(distanceArr)).argsort()[:1000]
        else:
            indices = np.where(pvals <= significanceThreshold)[0]

        locations = np.concatenate((locationArr[indices], distanceArr[indices].reshape(len(indices), 1), maxDiffArr[indices].reshape(len(indices), 1)), axis=1)

        # Iterate until all is merged
        while(hasAdjacent(locations)):
            locations = mergeAdjacent(locations)
            
        # Write all the locations to the file
        outTemplate = "{0[0]}\t{0[1]}\t{0[2]}\t{1}\t{2}\t{3}\n"
        outString = "".join(outTemplate.format(locations[i], nameArr[int(float(locations[i, 4])) - 1], abs(float(locations[i, 3])), findSign(float(locations[i, 3]))) for i in range(locations.shape[0]))
        f.write(outString)


# Helper function for determining when to stop merging roiURL loci
def hasAdjacent(locationArr):
    # Checks each location against every other location
    for i in range(locationArr.shape[0]):
        for j in range(locationArr.shape[0]):
            # If the chromosomes are the same and they are adjacent return True
            # Also check if the distance is in the same direction
            if locationArr[i, 0] == locationArr[j, 0] and (int(locationArr[i, 2]) - int(locationArr[j, 1]) == 0 or int(locationArr[j, 2]) - int(locationArr[i, 1]) == 0) and np.sign(float(locationArr[i, 3])) == np.sign(float(locationArr[j, 3])):
                return True
    # If we have gotten through everything and not found adjacent locations, return false
    return False


# Helper function for merging adjacent loci in the roiURL txt file
def mergeAdjacent(locationArr):
    for i in range(locationArr.shape[0]):
        for j in range(locationArr.shape[0]):
            # If the chromosomes are the same, they are adjacent, and their distances are in the same direction merge and delete the originals
            if locationArr[i, 0] == locationArr[j, 0] and int(locationArr[i, 2]) - int(locationArr[j, 1]) == 0 and np.sign(float(locationArr[i, 3])) == np.sign(float(locationArr[j, 3])):
                mergedLocation = np.array([locationArr[i, 0], locationArr[i, 1], locationArr[j, 2], locationArr[i, 3], locationArr[i, 4]]).reshape(1, 5)
                locationArr = np.delete(locationArr, [i, j], axis=0)
                locationArr = np.insert(locationArr, i, mergedLocation, axis=0)
                return locationArr
            elif locationArr[i, 0] == locationArr[j, 0] and int(locationArr[j, 2]) - int(locationArr[i, 1]) == 0 and np.sign(float(locationArr[i, 3])) == np.sign(float(locationArr[j, 3])):
                mergedLocation = np.array([locationArr[i, 0], locationArr[j, 1], locationArr[i, 2], locationArr[i, 3], locationArr[i, 4]]).reshape(1, 5)
                locationArr = np.delete(locationArr, [i, j], axis=0)
                locationArr = np.insert(locationArr, i, mergedLocation, axis=0)
                return locationArr
    return locationArr


# Helper function for sendRoiUrl
def findSign(x):
    if (x >= 0):
        return "+"
    else:
        return "-"


# Helper for slurm to send boolean values
def strToBool(string):
    if string == 'True':
        return True
    elif string == 'False':
        return False
    else:
        raise ValueError("Invalid boolean string")


if __name__ == "__main__":
    main(argv[1], argv[2], int(argv[3]), argv[4], argv[5], int(argv[6]), strToBool(argv[7]), int(argv[8]), int(argv[9]))