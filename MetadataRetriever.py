import subprocess
import re
from elftools.elf.elffile import ELFFile
from RegionRetriever import RegionRetriever

class MetadataRetriever:
    def __init__(self, elfFile, mapFile, regions=None, nmPrefix=""):
        if None == regions:
            memMapRetriever = RegionRetriever(elfFile, mapFile)
            regions = memMapRetriever.GetRegions()
        self.regions = regions

        def buildVmaToLmaRanges(elfFile):
            # A PT_LOAD segment's p_vaddr is where its content runs (VMA) and
            # p_paddr is where it is stored/loaded (LMA); they differ e.g. for
            # .data placed in flash (LMA) but executed from RAM (VMA) after the
            # startup code copies it. For an address inside such a segment,
            # LMA = VMA + (p_paddr - p_vaddr); elsewhere (offset 0) LMA == VMA.
            ranges = []
            with open(elfFile, 'rb') as f:
                for segment in ELFFile(f).iter_segments():
                    if 'PT_LOAD' == segment.header['p_type'] and segment.header['p_memsz'] > 0:
                        vaddr = segment.header['p_vaddr']
                        paddr = segment.header['p_paddr']
                        ranges.append((vaddr, vaddr + segment.header['p_memsz'], paddr - vaddr))
            return ranges

        self.vmaToLmaRanges = buildVmaToLmaRanges(elfFile)

        def retreiveSymbolLines(nmPrefix, elfFile):
            # nm -S omits the size column entirely (not "00000000") for a symbol
            # whose recorded ELF size is 0 - e.g. hand-written assembly routines
            # that never emitted a .size directive (memchr-style libc internals
            # are a common real-world case). The size field is therefore made
            # optional here so such symbols are not silently dropped: they are
            # real code/data occupying real bytes, just of unknown extent to nm.
            # Type 'A' (absolute) is explicitly excluded from that no-size
            # relaxation: those are linker-script constants (e.g. __top_FLASH,
            # a computed ORIGIN+LENGTH), not actual bytes anywhere in memory,
            # and letting them into the gap-detection address stream corrupts
            # it (a constant can coincidentally fall inside a real gap).
            cmdLine= (nmPrefix + "nm -s -n -S -l --defined-only " + elfFile +
                      " | grep -E \"^[[:xdigit:]]{8} ([[:xdigit:]]{8} )?[[:alpha:]] \"" +
                      " | grep -v -E \"^[[:xdigit:]]{8} A \"")
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

    def vmaToLma(self, addr):
        for vmaStart, vmaEnd, offset in self.vmaToLmaRanges:
            if vmaStart <= addr < vmaEnd:
                return addr + offset
        return addr

    def hasStringCoverage(self, gapStart, gapEnd):
        return any(
            element["isString"] and element["addr"] < gapEnd and (element["addr"] + element["dim"]) > gapStart
            for element in self.memoryMapList
        )

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
            # A lone letter in the size slot means nm omitted the size column
            # (see retreiveSymbolLines): the symbol's real size is unknown, not 0
            # bytes of content - it still occupies space up to whatever follows.
            if re.match(r'^[A-Za-z]$', fields[1]):
                symbolData["dim"] = 0
                symbolData["attr"] = fields[1]
                symbolData["name"] = fields[2]
                fileField = fields[3] if len(fields) > 3 else None
            else:
                symbolData["dim"] = int(fields[1], 16)
                symbolData["attr"] = fields[2]
                symbolData["name"] = fields[3]
                fileField = fields[4] if len(fields) > 4 else None
            symbolData["fill"] = False

            crossRefFile = ""
            if 0 == symbolData["dim"]:
                # A symbol nm could not size usually has no dedicated debug info
                # of its own either (hand-written assembly routines, aliases),
                # so nm -l's "nearest line" guess for it is frequently wrong -
                # confirmed e.g. for libc's assembly memchr(), which nm -l
                # attributes to an unrelated CMSIS header it happens to sit
                # next to in the link. The Cross Reference Table's defining-.o
                # entry is more trustworthy here, so prefer it when available.
                crossRefFile = self.crossRefDict.get(symbolData["name"], "")

            if crossRefFile:
                symbolData["file"] = crossRefFile
                symbolData["line"] = 0
            elif fileField is not None:
                p = re.compile(r"^.*:\d+$")
                if p.match(fileField):
                    symbolData["file"] = ':'.join(fileField.split(':')[:-1])
                    symbolData["line"] = int(fileField.split(':')[-1])
                else:
                    symbolData["file"] = fileField
                    symbolData["line"] = 0
            else:
                symbolData["line"] = 0
                # if nm fails to retreive file info related to a symbol we try to find it in
                # the cross reference section of map file.
                symbolData["file"] = self.crossRefDict.get(symbolData["name"], "")
                if "" == symbolData["file"]:
                    # if also cross reference section does not contain file information we try
                    # to find it in the memory map section. The infos can be all in 1 line or can
                    # be splitted in two.
                    symbolData["file"] = getFileFromMemoryMap(symbolData["addr"], symbolData["dim"], self.memoryMapList)
            symbolData["region"] = findRegion(symbolData["addr"], self.regions)
            symbolData["lma"] = self.vmaToLma(symbolData["addr"])
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
                    "lma": self.vmaToLma(addr),
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
        # Per-region high-water mark of "addr + dim" already accounted for.
        # A size-less symbol (dim 0, see retreiveSymbolMetadata) can sit
        # *inside* an earlier, properly-sized symbol's range (e.g. a static
        # local nm couldn't size, declared inside a function's own bytes, or
        # an internal entry point inside one bigger assembly routine) - using
        # only the immediately preceding list entry's end as the next gap's
        # start would then walk the cursor backwards and double-count bytes
        # already covered by that earlier symbol. The watermark never moves
        # backwards, so it is immune to that regardless of how the size-less
        # symbols are interleaved with properly-sized ones.
        regionWatermark = {}
        firstSymbol = retreiveSymbolMetadata(self.symbolLineList[0])
        symbolsList.append(firstSymbol)
        regionWatermark[firstSymbol["region"]] = firstSymbol["addr"] + firstSymbol["dim"]
        for line in self.symbolLineList[1:]:
            symbolData = retreiveSymbolMetadata(line)
            region = symbolData["region"]
            watermark = regionWatermark.get(region)
            if watermark is not None and watermark < symbolData["addr"]:
                gapStart = watermark
                gapEnd = symbolData["addr"]
                lastEntry = symbolsList[-1] if symbolsList else None
                # If the gap starts exactly where a size-less symbol (dim 0)
                # sits, there is no better evidence for those bytes than "they
                # belong to the symbol that starts right here" - infer its
                # size up to this next known boundary instead of reporting an
                # anonymous, unattributed *fill*/*str* immediately after it
                # (confirmed on real firmware: nm's size-less memchr() was
                # followed by a same-address *fill* that was actually its own
                # Thumb code). This is a best-effort guess, not ground truth:
                # genuine padding between the symbol and the next one would be
                # counted as part of it too. Map-confirmed string coverage is
                # hard evidence and always takes precedence over this guess.
                if (lastEntry is not None and lastEntry["region"] == region and
                        lastEntry["dim"] == 0 and lastEntry["addr"] == gapStart and
                        not self.hasStringCoverage(gapStart, gapEnd)):
                    lastEntry["dim"] = gapEnd - gapStart
                else:
                    symbolsList.extend(buildGapEntries(region, gapStart, gapEnd))
            symbolsList.append(symbolData)
            symbolEnd = symbolData["addr"] + symbolData["dim"]
            regionWatermark[region] = max(watermark, symbolEnd) if watermark is not None else symbolEnd

        return symbolsList