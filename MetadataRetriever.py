import subprocess
import re
from RegionRetriever import RegionRetriever

class MetadataRetriever:
    def __init__(self, elfFile, mapFile, regions=None, nmPrefix=""):
        if None == regions:
            memMapRetriever = RegionRetriever(elfFile, mapFile)
            regions = memMapRetriever.GetRegions()
        self.regions = regions

        def retreiveSymbolLines(nmPrefix, elfFile):
            cmdLine= nmPrefix + "nm -s -n -S -l --defined-only " +elfFile+ " | grep -E \"^[[:xdigit:]]{8} [[:xdigit:]]{8} [[:alpha:]] \""
            process = subprocess.run(cmdLine, shell=True, stdout=subprocess.PIPE)
            process.check_returncode()
            return process.stdout.decode("utf-8").strip().splitlines()

        self.symbolLineList = retreiveSymbolLines(nmPrefix, elfFile)

        def getMemoryMapSlice(mapFile):
            cmdLine="sed -ne '/^Linker script and memory map$/,/^OUTPUT(.*)$/{ s/^[[:space:]][^[:space:]]*[[:space:]]\\+\\(0x[[:xdigit:]]\\+[[:space:]]\\+0x[[:xdigit:]]\\+[[:space:]]\\+[^[:space:]]\\+\\.o\\()\\|\\)\\)$/\\1/p}' " + mapFile + " | sort"
            process = subprocess.run(cmdLine, shell=True, stdout=subprocess.PIPE)
            MemoryMapList = []
            if(process.returncode == 0):
                MemoryMapText = process.stdout.decode("utf-8").strip().splitlines()
                for line in MemoryMapText:
                    MemoryMapDict = {}
                    fields = line.split()
                    MemoryMapDict["dim"] = int(fields[1], 16)
                    if 0 == MemoryMapDict["dim"]:
                        continue
                    MemoryMapDict["addr"] = int(fields[0], 16)
                    MemoryMapDict["file"] = fields[2]
                    MemoryMapList.append(MemoryMapDict)
            return MemoryMapList

        self.memoryMapList = getMemoryMapSlice(mapFile)

        def getCrossRefSection(mapFile):
            cmdLine="sed -ne '/^Cross Reference Table$/,${ /^Symbol[[:space:]]\\+File$/n; /^[^[:space:]]\\+[[:space:]]\\+[^[:space:]]\\+$/p; } ' " + mapFile
            process = subprocess.run(cmdLine, shell=True, stdout=subprocess.PIPE)
            crossRefDict = {}
            if(process.returncode == 0):
                crossRefRawLines = process.stdout.decode("utf-8").strip().splitlines()
                for line in crossRefRawLines:
                    element = line.split()
                    crossRefDict[element[0]] = element[1]
            return crossRefDict

        self.crossRefDict = getCrossRefSection(mapFile)

    def retreiveSymbols(self):
        def retreiveSymbolMetadata(line):
            def getFileFromMemoryMap(addr, dim, MemoryMapList):
                for element in MemoryMapList:
                    if addr >= element["addr"] and (addr + dim) <= (element["addr"] + element["dim"]):
                        return element["file"]
                return ""
            def findRegion(addr, Regions):
                for region in Regions:
                    metadata = Regions[region]
                    if addr >= metadata["Origin"] and addr < (metadata["Origin"] + metadata["Length"]):
                        return region
                return "unknown"
            fields=line.split()
            symbolData = {}
            symbolData["addr"] = int(fields[0], 16)
            symbolData["dim"] = int(fields[1], 16)
            symbolData["attr"] = fields[2]
            symbolData["name"] = fields[3]
            symbolData["fill"] = False
            if(len(fields) == 4):
                symbolData["line"] = 0
                # if nm fails to retreive file info related to a symbol we try to find it in
                # the cross reference section of map file.
                symbolData["file"] = self.crossRefDict.get(symbolData["name"], "")
                if "" == symbolData["file"]:
                    # if also cross reference section does not contain file information we try
                    # to find it in the memory map section. The infos can be all in 1 line or can
                    # be splitted in two.
                    symbolData["file"] = getFileFromMemoryMap(symbolData["addr"], symbolData["dim"], self.memoryMapList)
            else:
                p = re.compile("^.*:\d+$")
                if p.match(fields[4]):
                    symbolData["file"] = ':'.join(fields[4].split(':')[:-1])
                    symbolData["line"] = int(fields[4].split(':')[-1])
                else:
                    symbolData["file"] = fields[4]
                    symbolData["line"] = 0
            symbolData["region"] = findRegion(symbolData["addr"], self.regions)
            return symbolData

        symbolsList = []
        symbolsList.append(retreiveSymbolMetadata(self.symbolLineList[0]))
        for line in self.symbolLineList[1:]:
            symbolData = retreiveSymbolMetadata(line)
            if symbolData["region"] == symbolsList[-1]["region"] and (symbolsList[-1]["addr"] + symbolsList[-1]["dim"]) < symbolData["addr"]:
                fillEntry = {}
                fillEntry["name"] = "*fill*"
                fillEntry["region"] = symbolData["region"]
                fillEntry["addr"] = symbolsList[-1]["addr"] + symbolsList[-1]["dim"]
                fillEntry["dim"] = symbolData["addr"] - fillEntry["addr"]
                fillEntry["attr"] = " "
                fillEntry["file"] = ""
                fillEntry["line"] = 0
                fillEntry["fill"] = True
                symbolsList.append(fillEntry)
            symbolsList.append(symbolData)

        return symbolsList