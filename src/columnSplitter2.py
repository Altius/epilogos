import sys
from pathlib import Path
import random

def main(filename, file1name, file2name):

    # Take in all file 1 genomes
    file1 = Path(file1name)
    group1 = []
    with open(file1, 'r') as f1:
        lines = f1.readlines()
        for line in lines:
            group1.append(line.split("|")[-1].strip())

    # Take in all file 2 genomes
    file2 = Path(file2name)
    group2 = []
    with open(file2, 'r') as f2:
        lines = f2.readlines()
        for line in lines:
            group2.append(line.split("|")[-1].strip())

    print(str(file1).split("/")[-2], group1)
    print(str(file2).split("/")[-2], group2)
    print()
    print()

    # Go through the master genome file and if a genome matches one of the genomes in group 1 or 2, append its column number to a dictionary for the groups
    file = Path(filename)
    listOfBoth = []
    with open(file, 'r') as f:
        lines = f.readlines()
        genomeNumber = 4
        groupDictionary = {"group1": [], "group2": []}
        for line in lines:
            genomeType = line.split("|")[-1].strip()
            if genomeType in group1:
                groupDictionary["group1"].append(genomeNumber)
                listOfBoth.append(genomeNumber)
            if genomeType in group2:
                groupDictionary["group2"].append(genomeNumber)
                listOfBoth.append(genomeNumber)
            genomeNumber += 1

    print(str(file1).split("/")[-2], groupDictionary["group1"])
    print(str(file2).split("/")[-2], groupDictionary["group2"])
    print()
    print()

    print(str(file1).split("/")[-2] + str(file2).split("/")[-2] + ": " + str(listOfBoth).strip('[]').replace(" ", ""))
    print()
    print()

    # Shuffle the lists
    shuffledList = groupDictionary["group1"] + groupDictionary["group2"]
    random.shuffle(shuffledList)
    print("{}\t1,2,3,{}".format(str(file1).split("/")[-2], str(shuffledList[:len(groupDictionary["group1"])]).strip('[]').replace(" ", "")))
    print()
    print("{}\t1,2,3,{}".format(str(file2).split("/")[-2], str(shuffledList[len(groupDictionary["group1"]):]).strip('[]').replace(" ", "")))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])