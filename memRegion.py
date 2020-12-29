#!/usr/bin/env python3

from __future__ import print_function
import sys
import argparse
from RegionRetriever import RegionRetriever

parser = argparse.ArgumentParser()
parser.add_argument("--human", help="print human readable", action='store_true', default=False)
parser.add_argument("mapfile", help="input map file")

args = parser.parse_args()

try:
    memMapRetriever = RegionRetriever(mapFile=args.mapfile)
except:
    print("Error occurred! Does %s file exist?" % args.mapfile)
    sys.exit()

if args.human :
    memDict = memMapRetriever.GetRegions()
    print("%-16s %-18s %-18s %s" % ("Name","Origin","Length","Attributes") )
    for RegionName in memDict :
        regionDesc = memDict[RegionName]
        print("%-16s 0x%016x 0x%016x %s" % ((RegionName,) + tuple(regionDesc.values())))
else :
    print(memMapRetriever.GetRegionsJson())
