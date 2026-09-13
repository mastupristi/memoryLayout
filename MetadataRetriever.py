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
            # An input-section stanza in the "Linker script and memory map" can be
            # printed on a single line ("name addr size file") or, when the section
            # name is too long to fit the column, wrapped on two lines (name alone,
            # then "addr size file" indented on the next line). Both forms are parsed
            # here so long names (e.g. mergeable string-literal sections, which are
            # almost always long) are not silently dropped.
            startPattern = re.compile(r"^Linker script and memory map$")
            endPattern = re.compile(r"^OUTPUT\(.*\)$")
            nameOnlyPattern = re.compile(r"^ (\.\S+)$")
            entryPattern = re.compile(
                r"^\s*(?:(\.\S+)\s+)?(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(\S+(?:\.o|\.a\([^()]+\.o\)))\s*$"
            )
            # GCC names mergeable string-literal sections ".rodata[.<func>].strN.M"
            # (N = element size, M = alignment), e.g. ".rodata.main.str1.1".
            strSectionPattern = re.compile(r"\.str\d+\.\d+$")

            MemoryMapList = []
            pendingName = None
            inSection = False
            with open(mapFile, "r") as a_file:
                for rawLine in a_file:
                    line = rawLine.rstrip("\n")
                    if not inSection:
                        if startPattern.match(line):
                            inSection = True
                        continue
                    if endPattern.match(line):
                        break

                    nameMatch = nameOnlyPattern.match(line)
                    if nameMatch:
                        pendingName = nameMatch.group(1)
                        continue

                    entryMatch = entryPattern.match(line)
                    if entryMatch:
                        sectionName = entryMatch.group(1) or pendingName
                        pendingName = None
                        dim = int(entryMatch.group(3), 16)
                        if 0 == dim:
                            continue
                        MemoryMapList.append({
                            "addr": int(entryMatch.group(2), 16),
                            "dim": dim,
                            "file": entryMatch.group(4),
                            "isString": bool(sectionName and strSectionPattern.search(sectionName)),
                        })
                        continue

                    pendingName = None
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
                p = re.compile(r"^.*:\d+$")
                if p.match(fields[4]):
                    symbolData["file"] = ':'.join(fields[4].split(':')[:-1])
                    symbolData["line"] = int(fields[4].split(':')[-1])
                else:
                    symbolData["file"] = fields[4]
                    symbolData["line"] = 0
            symbolData["region"] = findRegion(symbolData["addr"], self.regions)
            return symbolData

        def buildGapEntries(region, gapStart, gapEnd):
            # Symbols have no entry for string literals (nm never emits one for
            # them), so a gap between two consecutive symbols may in fact be a
            # mergeable string-literal section rather than alignment padding.
            # Split the gap against any *fill*/*str* boundaries the map file's
            # per-input-section listing (self.memoryMapList) can tell us about,
            # instead of always reporting it as a single opaque *fill* block.
            def makeEntry(name, addr, dim, file, fill):
                return {
                    "name": name,
                    "region": region,
                    "addr": addr,
                    "dim": dim,
                    "attr": " ",
                    "file": file,
                    "line": 0,
                    "fill": fill,
                }

            # Under -fmerge-constants ld can (and, in practice, routinely does)
            # report many different input ".strN.M" sections at the very same
            # output address: they were deduplicated/merged into one physical
            # copy, but the map still lists each contributor with its own
            # (pre-merge) size, so these ranges massively overlap each other.
            # There is no way to recover exact non-overlapping per-contributor
            # byte ranges from the map alone, so contributors are coalesced
            # into non-overlapping *str* spans (standard interval merge)
            # instead of naively laying them out back-to-back.
            clippedRanges = []
            for element in self.memoryMapList:
                if not element["isString"]:
                    continue
                segStart = max(gapStart, element["addr"])
                segEnd = min(gapEnd, element["addr"] + element["dim"])
                if segEnd > segStart:
                    clippedRanges.append((segStart, segEnd, element["file"]))
            clippedRanges.sort(key=lambda t: t[0])

            mergedRanges = []
            for segStart, segEnd, file in clippedRanges:
                # Merge only on genuine overlap (strict '<'), not mere adjacency:
                # touching-but-disjoint ranges carry an exact, unambiguous split
                # point (e.g. two different functions' non-deduplicated string
                # pools placed back-to-back), which is worth keeping when it's
                # free - only real overlap (from SHF_MERGE deduplication, where
                # the split point genuinely can't be recovered) forces a merge.
                if mergedRanges and segStart < mergedRanges[-1][1]:
                    mergedRanges[-1][1] = max(mergedRanges[-1][1], segEnd)
                    mergedRanges[-1][2].add(file)
                else:
                    mergedRanges.append([segStart, segEnd, {file}])

            entries = []
            cursor = gapStart
            for segStart, segEnd, files in mergedRanges:
                if segStart > cursor:
                    entries.append(makeEntry("*fill*", cursor, segStart - cursor, "", True))
                fileList = sorted(files)
                if len(fileList) > 1:
                    # ',' would break the csv output type, and a full file list
                    # can get very long when many TUs share deduplicated strings.
                    fileField = "%s (+%d other files)" % (fileList[0], len(fileList) - 1)
                else:
                    fileField = fileList[0]
                entries.append(makeEntry("*str*", segStart, segEnd - segStart, fileField, False))
                cursor = segEnd
            if cursor < gapEnd:
                entries.append(makeEntry("*fill*", cursor, gapEnd - cursor, "", True))

            # Sanity check: entries must exactly and contiguously tile [gapStart,
            # gapEnd) with strictly positive, non-overlapping sizes. If this ever
            # trips, the interval merge above has a bug - fail loudly rather than
            # silently emitting bogus (zero/negative-size, non-monotonic) entries.
            cursor = gapStart
            for entry in entries:
                assert entry["addr"] == cursor and entry["dim"] > 0, \
                    "inconsistent gap entry %r (expected addr %#x)" % (entry, cursor)
                cursor += entry["dim"]
            assert cursor == gapEnd, "gap entries do not cover [%#x, %#x)" % (gapStart, gapEnd)

            return entries

        symbolsList = []
        symbolsList.append(retreiveSymbolMetadata(self.symbolLineList[0]))
        for line in self.symbolLineList[1:]:
            symbolData = retreiveSymbolMetadata(line)
            if symbolData["region"] == symbolsList[-1]["region"] and (symbolsList[-1]["addr"] + symbolsList[-1]["dim"]) < symbolData["addr"]:
                gapStart = symbolsList[-1]["addr"] + symbolsList[-1]["dim"]
                gapEnd = symbolData["addr"]
                symbolsList.extend(buildGapEntries(symbolData["region"], gapStart, gapEnd))
            symbolsList.append(symbolData)

        return symbolsList