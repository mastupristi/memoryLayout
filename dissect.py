#!/usr/bin/env python3

# is required that the GNU ARM toolchais is in PATH

import argparse
import sys
from RegionRetriever import RegionRetriever
from MetadataRetriever import MetadataRetriever


class LineEmitter:
    def __init__(self, regionStringExtent=16, symbolStringExtent=40, csv=False):
        charactersForRegion = max(regionStringExtent, 16)
        charactersForSymbol = max(symbolStringExtent, 40)
        self.formatStr = "%%%ds %%10s %%12s %%9s %%5s %%%ds %%s" % (charactersForRegion, charactersForSymbol)
        self.csv = csv
    
    def emitLine(self, elementlist, file2out):
        if(True == self.csv):
            stroutline = ','.join(elementlist)
        else:
            stroutline = self.formatStr % tuple(elementlist)
        file2out.write(stroutline+"\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--type", help="output type (default: normal)", choices=['normal', 'csv'], default='normal')
    parser.add_argument("-o", "--out", help="out file (default: stdout)", type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument("-r", "--region", help="memory region to dissect (default: all)", default='all', metavar='REG')
    parser.add_argument("-u", "--uniq", help="filter symbols @address already populated", action='store_true')
    parser.add_argument("-f", "--fill", help="try to guess the *fill* fields", action='store_true')
    parser.add_argument("-l", "--noline", help="remove any line number from files", action='store_true')
    parser.add_argument("-p", "--prefix", help="prefix for nm tool (e.g. arm-none-eabi-, default: \"\")", default='', metavar='PREFIX')
    parser.add_argument("elffile", help="input elf file")
    parser.add_argument("mapfile", help="input map file")

    args = parser.parse_args()
    if args.type == 'csv':
        csv = True
    else:
        csv = False

    try:
        memMapRetriever = RegionRetriever(mapFile=args.mapfile)
    except:
        print("Error occurred! Does %s file exist?" % args.mapfile)
        sys.exit()
    Regions = memMapRetriever.GetRegions()

    metadataRetriever = MetadataRetriever(args.elffile, args.mapfile, Regions, args.prefix)
    symbolList = metadataRetriever.retreiveSymbols()

    regionNameMaxLen = len(max(Regions.keys(), key=len))

    symbolNameMaxLen = len(max([sym["name"] for sym in symbolList], key=len))

    if "all" != args.region:
        if args.region in Regions.keys():
            symbolList = [d for d in symbolList if args.region == d["region"]]
        else:
            print("Region %s does not exist in %s" % (args.region, args.elffile))
            sys.exit()

    emitter = LineEmitter(regionNameMaxLen, symbolNameMaxLen, csv)

    fields = [  "Region",
                "addr(hex)",
                "addr(dec)",
                "size(hex)",
                "type",
                "symbol",
                "path"]

    emitter.emitLine(fields, args.out)

    lastaddr = -1
    for symbol in symbolList:
        if args.uniq and lastaddr == symbol["addr"]:
            continue
        if (not args.fill) and symbol["fill"]:
            continue
        if symbol["file"] != "":
            fileField = symbol["file"]
            if False == args.noline and symbol["line"] > 0:
                fileField += ":%d" % symbol["line"]
        else:
            fileField = ""
        
        fields = [  symbol["region"],
                    "0x%08x" % symbol["addr"],
                    "%d" % symbol["addr"],
                    "%d" % symbol["dim"],
                    "%c" % symbol["attr"],
                    symbol["name"],
                    fileField
        ]
        emitter.emitLine(fields, args.out)
        lastaddr = symbol["addr"]

    
if __name__ == '__main__':
    main()

