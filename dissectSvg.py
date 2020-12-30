import argparse
import sys
import svgwrite
from RegionRetriever import RegionRetriever
from MetadataRetriever import MetadataRetriever


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--prefix", help="prefix for nm tool (e.g. arm-none-eabi-, default: \"\")", default='', metavar='PREFIX')
    parser.add_argument("elffile", help="input elf file")
    parser.add_argument("mapfile", help="input map file")
    parser.add_argument("region", help="memory region to dissect")
    parser.add_argument("output", help="output file")

    args = parser.parse_args()

    try:
        memMapRetriever = RegionRetriever(mapFile=args.mapfile)
    except:
        print("Error occurred! Does %s file exist?" % args.mapfile)
        sys.exit()
    Regions = memMapRetriever.GetRegions()

    metadataRetriever = MetadataRetriever(args.elffile, args.mapfile, Regions, args.prefix)
    symbolList = metadataRetriever.retreiveSymbols()

    if args.region in Regions.keys():
        symbolList = [d for d in symbolList if args.region == d["region"]]
    else:
        print("Region %s does not exist in %s" % (args.region, args.elffile))
        sys.exit()

    regionOffset = Regions[args.region]["Origin"]

    div = 160
    heigth = Regions[args.region]["Length"]/div
    width = (heigth)/8

    bgColor = svgwrite.rgb(75, 75, 85, '%')

    fgColor = [ svgwrite.rgb(70, 50, 50, '%'),
                svgwrite.rgb(50, 70, 50, '%'),
                svgwrite.rgb(50, 50, 70, '%'),
                svgwrite.rgb(70, 70, 50, '%')]
    
    dwg = svgwrite.Drawing(args.output, profile='full')
    dwg.add(dwg.rect((0, 0), (width, heigth), fill=bgColor))

    fgColorVectorDim = len(fgColor)
    fgColorIndex = 0
    lastaddr = -1
    for symbol in symbolList:
        if lastaddr == symbol["addr"]:
            continue
        if symbol["fill"]:
            continue

        symbolY = (symbol["addr"] - regionOffset) / div

        dwg.add(dwg.rect((0, symbolY), (width, symbol["dim"]/div), fill=fgColor[fgColorIndex]))

        lastaddr = symbol["addr"]
        fgColorIndex += 1
        if fgColorIndex >= fgColorVectorDim:
            fgColorIndex = 0

    dwg.save()
    
if __name__ == '__main__':
    main()