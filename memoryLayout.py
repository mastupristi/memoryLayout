#!/usr/bin/env python3

from __future__ import print_function
import sys
import argparse
from RegionRetriever import RegionRetriever

# If pyelftools is not installed, the example can also run from the root or
# examples/ dir of the source distribution.
sys.path[0:0] = ['.', '..']

from elftools.elf.elffile import ELFFile
from elftools.elf.constants import SH_FLAGS

def addr2region(addr, memConf) :
    for regionName in memConf:
        regionDesc = memConf[regionName]
        if addr >= regionDesc['Origin'] and addr < (regionDesc['Origin'] + regionDesc['Length']) :
            return regionName
    return None

def buildLoadMap(elfFileName, memConf):
    memMapConf = {}
    with open(elfFileName, 'rb') as f:
        elfFileObj = ELFFile(f)
        for segment in elfFileObj.iter_segments():
            if ( 'PT_LOAD' == segment.header['p_type'] and
                segment.header['p_vaddr'] != segment.header['p_paddr']):
                for section in elfFileObj.iter_sections():
                    if (    not section.is_null() and
                            not ((section['sh_flags'] & SH_FLAGS.SHF_TLS) != 0 and
                                section['sh_type'] == 'SHT_NOBITS' and
                                segment['p_type'] != 'PT_TLS') and
                            segment.section_in_segment(section)):
                        loadAddr = 0
                        if ( (section['sh_flags'] & SH_FLAGS.SHF_ALLOC) != 0 and
                                section['sh_type'] != 'SHT_NOBITS') :
                            loadAddr = segment.header['p_paddr'] + section['sh_addr'] - segment.header['p_vaddr']
                        else :
                            loadAddr = segment.header['p_paddr'] + section['sh_offset'] - segment.header['p_offset']
                        memMapConf[section.name] = (addr2region(segment.header['p_paddr'], memConf), loadAddr)
    return memMapConf

def size2string(sz):
    if (sz & 0x3fffffff) == 0 :
        return "%10u GB" % (sz >> 30)
    elif (sz & 0xfffff) == 0 :
        return "%10u MB" % (sz >> 20)
    elif (sz & 0x3ff) == 0 :
        return "%10u KB" % (sz >> 10)
    else :
        return " %10u B" % sz

def size2stringHumanReadable(sz):
    if (sz > 0x3fffffff) :
        return "%10s GB" % (("%.2f" % (sz / (1<<30))).rstrip('0.'))
    if (sz > 0xfffff) :
        return "%10s MB" % (("%.2f" % (sz / (1<<20))).rstrip('0.'))
    if (sz > 0x3ff) :
        return "%10s KB" % (("%.2f" % (sz / (1<<10))).rstrip('0.'))
    else :
        return " %10u B" % sz

def process_file(filename, verbose, rodata, percentages, humanReadable, debugReg, memConf):
    MemLayout = {}
    for regionName in memConf:
        MemLayout[regionName] = {".text": 0, ".rodata": 0, ".data": 0, ".bss": 0, "LoadMap": 0, "Tot": 0}
    memMapConf = buildLoadMap(filename, memConf)
    with open(filename, 'rb') as f:
        for sect in ELFFile(f).iter_sections():
            if 0 != (sect.header['sh_flags'] & SH_FLAGS.SHF_ALLOC) :
                MemRegion = addr2region(sect.header['sh_addr'], memConf)
                if (0 != (sect.header['sh_flags'] & SH_FLAGS.SHF_EXECINSTR)): # .text
                    section = '.text'
                elif (0 == (sect.header['sh_flags'] & SH_FLAGS.SHF_WRITE)) :
                    if rodata:
                        section = '.rodata'
                    else :
                        section = '.text'
                elif (sect.header['sh_type'] == 'SHT_NOBITS'): # .bss
                    section = '.bss'
                else : # .data
                    section = '.data'
                aligmentAdj = MemLayout[MemRegion]['Tot']%sect.header['sh_addralign']
                if aligmentAdj != 0 :
                    aligmentAdj = sect.header['sh_addralign']-aligmentAdj
                    adjStr = " + %d bytes due to alignment %d" % (aligmentAdj, sect.header['sh_addralign'])
                else:
                    adjStr = ""

                if debugReg and debugReg == MemRegion :
                    print("%16s @ 0x%.8x" % (sect.name, memConf[debugReg]['Origin'] + MemLayout[MemRegion]['Tot'] + aligmentAdj))
                actualSize = sect.header['sh_size'] + aligmentAdj
                MemLayout[MemRegion]['Tot'] += actualSize
                MemLayout[MemRegion][section] += actualSize

                if verbose:
                    print("adding %s section to %s%s (%d bytes%s)" %(sect.name, MemRegion, section, sect.header['sh_size'], adjStr))
        for sect in ELFFile(f).iter_sections():
            if 0 != (sect.header['sh_flags'] & SH_FLAGS.SHF_ALLOC) :
                if sect.name in memMapConf and sect.header['sh_type'] != 'SHT_NOBITS':
                    MapRegion = memMapConf[sect.name][0]
                    SectionLoadAddr = memMapConf[sect.name][1]
                    if (SectionLoadAddr - memConf[MapRegion]['Origin']) != MemLayout[MapRegion]['Tot'] :
                        aligmentAdj = (SectionLoadAddr - memConf[MapRegion]['Origin']) - MemLayout[MapRegion]['Tot']
                        adjStr = " + %d bytes due to alignment %d" % (aligmentAdj, sect.header['sh_addralign'])
                    else:
                        aligmentAdj = 0
                        adjStr = ""

                    if debugReg and debugReg == MapRegion :
                        print("%16s @ 0x%.8x" % (sect.name, SectionLoadAddr))
                    actualSize = sect.header['sh_size'] + aligmentAdj
                    MemLayout[MapRegion]['Tot'] += actualSize
                    MemLayout[MapRegion]['LoadMap'] += actualSize

                    if verbose:
                        print("load %s section to %s%s (%d bytes%s)" %(sect.name, MapRegion, section, sect.header['sh_size'], adjStr))

        RegionNameLen = max([len(x) for x in MemLayout.keys()] + [16,])

        sizeStringArray = {}
        if humanReadable :
            for memReg in MemLayout :
                sizeStringArray[memReg] = [size2stringHumanReadable(sz) for sz in MemLayout[memReg].values()]
        else :
            for memReg in MemLayout :
                sizeStringArray[memReg] = [(" %10d B" % sz) for sz in MemLayout[memReg].values()]

        if percentages :
            if rodata:
                print("%-*s                    .text                .rodata                  .data                   .bss                LoadMap        Total  Region Size  %%age Used" % (RegionNameLen, "Memory region"))
                for memReg in MemLayout :
                    percentInterleaved = sum(zip(sizeStringArray[memReg],[100 * x / memConf[memReg]['Length'] for x in MemLayout[memReg].values()]),())
                    percentInterleaved = percentInterleaved[:-1] + (size2string(memConf[memReg]['Length']),) + percentInterleaved[-1:]
                    print("%*s: %s (%6.2f%%)%s (%6.2f%%)%s (%6.2f%%)%s (%6.2f%%)%s (%6.2f%%)%s%s    %6.2f%%" % ((RegionNameLen, memReg,) + percentInterleaved))
            else:
                print("%-*s                    .text                  .data                   .bss                LoadMap        Total  Region Size  %%age Used" % (RegionNameLen, "Memory region"))
                for memReg in MemLayout :
                    percentInterleaved = sum(zip(sizeStringArray[memReg],[100 * x / memConf[memReg]['Length'] for x in MemLayout[memReg].values()]),())
                    percentInterleaved = percentInterleaved[:-1] + (size2string(memConf[memReg]['Length']),) + percentInterleaved[-1:]
                    print("%*s: %s (%6.2f%%)%s (%6.2f%%)%s (%6.2f%%)%s (%6.2f%%)%s%s    %6.2f%%" % ((RegionNameLen, memReg,) + percentInterleaved[:2] + percentInterleaved[4:]))
        else:
            if rodata:
                print("%-*s          .text      .rodata        .data         .bss      LoadMap        Total" % (RegionNameLen, "Memory region"))
                for memReg in MemLayout :
                    print("%*s: %s%s%s%s%s%s" % ((RegionNameLen, memReg,) + tuple(sizeStringArray[memReg])))
            else:
                print("%-*s          .text        .data         .bss      LoadMap        Total" % (RegionNameLen, "Memory region"))
                for memReg in MemLayout :
                    print("%*s: %s%s%s%s%s" % ((RegionNameLen, memReg,) + tuple(sizeStringArray[memReg])[:1] + tuple(sizeStringArray[memReg])[2:]))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(conflict_handler="resolve")
    parser.add_argument('-v', "--verbose", help="print some message", action='store_true', default=False)
    parser.add_argument('-ro', "--extract-rodata", help="unbundle .rodata infos", action='store_true', default=False)
    parser.add_argument('-p', "--percentages", help="print percentages", action='store_true', default=False)
    parser.add_argument('-dr', "--debug-region", help="some debug prints about REG memory region", default=None, metavar='REG')
    parser.add_argument('-h', "--human-readable", help="print human readable values", action='store_true', default=False)
    parser.add_argument("elffile", help="input elf file")
    parser.add_argument("mapfile", help="input map file (shoud be unused)", nargs='?', default=None)

    args = parser.parse_args()

    try:
        memMapRetriever = RegionRetriever(args.elffile, args.mapfile)
    except:
        print("elffile must exist and contain '.memory_configuration' section, or at least map file must be provided.", sys.exc_info()[0])
        sys.exit()
    
    memConf = memMapRetriever.GetRegions()

    process_file(args.elffile, args.verbose, args.extract_rodata, args.percentages, args.human_readable, args.debug_region, memConf)

