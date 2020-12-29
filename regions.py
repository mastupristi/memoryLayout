from RegionRetriever import RegionRetriever
import argparse
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("elffile", help="input elf file")
    parser.add_argument("mapfile", help="input map file", nargs='?', default=None)

    args = parser.parse_args()
    try:
        memMapRetriever = RegionRetriever(args.elffile, args.mapfile)
    except:
        print("elffile must exist and contain '.memory_configuration' section, or at least map file must be provided.", sys.exc_info()[0])
    else:
        print(*memMapRetriever.GetRegions().keys(), sep = "\n") 

if __name__ == '__main__':
    main()