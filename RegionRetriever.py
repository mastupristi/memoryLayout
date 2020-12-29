import json
import re
from elftools.elf.elffile import ELFFile

class RegionRetriever:
    def __init__(self, elfFile=None, mapFile=None):
        def retrieveMemoryConfFromMap(mapfile):
            patternIni = re.compile("^Memory Configuration$")
            patternMem = re.compile("^[A-Za-z0-9_\*]+\s+0x[0-9a-fA-F]{8,16} 0x[0-9a-fA-F]{8,16}\s*\w*$")
            keys = ("Origin","Length","Attributes")
            with open(mapfile, "r") as a_file:
                line = a_file.readline()
                while line:
                    matchObj = patternIni.match(line)
                    if matchObj:
                        break
                    line = a_file.readline()

                memDict = {}
                line = a_file.readline()
                while line:
                    matchObj = patternMem.match(line)
                    if matchObj:
                        memDesc = line.strip().split()
                        if "*default*" == memDesc[0]:
                            break
                        memDict[memDesc[0]] = dict(zip(keys, (int(memDesc[1], 16), int(memDesc[2], 16), memDesc[3])))
                    line = a_file.readline()
            return memDict

        def retrieveMemoryConfFromElf(elffile):
            memConf = None
            with open(elffile, 'rb') as f:
                sect = ELFFile(f).get_section_by_name(".memory_configuration")
                memConf = json.loads(sect.data())
            return memConf

        try:
            self.memConf = retrieveMemoryConfFromElf(elfFile)
        except:
            self.memConf = retrieveMemoryConfFromMap(mapFile)

    def GetRegionsJson(self):
        return json.dumps(self.memConf)

    def GetRegions(self):
        return self.memConf