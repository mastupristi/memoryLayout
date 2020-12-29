# Memory Layout

This project aims to extract more detailed information about the memory layout
of an elf file.

What we want is to know how the various memory regions are divided between
`.text` (code), `.data` (initialized data), `.bss` (uninitialized data).
Eventually also dissect further `.text` to highlight also `.rodata` (constant
data).<br>
In addition to this we would like to have the detail of the symbols, their
allocation in the regions and especially the source file where these symbols
are declared, or at least the `.o` file that contains the symbol. This allows
us to be able to find bottlenecks in memory usage: Which symbols are the _largest_
and which source file declares them. This allows us to do static profiling
of memory usage.

Using the tools available in the binutils, you can't dissect that deep.


## Examples

I started with SDK 2.5.1 for NXP i.MX RT1050. I took the example
`evkbimxrt1050_sai_interrupt_transfer` configured in two different ways:
- link-to-ram project
- flash project

In the repository I added also the elf files (with extension `.axf`) and the map files:

```
-rwxrwxr-x 1 max max 1948540 apr 17 13:19 evkbimxrt1050_sai_interrupt_transfer_flash.axf*
-rw-rw-r-- 1 max max  287069 apr 17 13:19 evkbimxrt1050_sai_interrupt_transfer_flash.map
-rwxrwxr-x 1 max max 1773648 apr 20 20:18 evkbimxrt1050_sai_interrupt_transfer_link-to-ram.axf*
-rw-rw-r-- 1 max max  285750 apr 20 20:18 evkbimxrt1050_sai_interrupt_transfer_link-to-ram.map
```

## Legacy information obtained with binutils

During the link `ld` can give some information with the parameter `-print-memory-usage`.
There is also the option to use the `size` command of the toolchain.

### link-to-ram project

The linker gives this information:

```
Memory region         Used Size  Region Size  %age Used
     BOARD_FLASH:          0 GB        64 MB      0.00%
        SRAM_ITC:       83384 B       128 KB     63.62%
        SRAM_DTC:        8796 B       128 KB      6.71%
         SRAM_OC:          0 GB       256 KB      0.00%
     BOARD_SDRAM:          0 GB        32 MB      0.00%
```

`size` conmmand says:

```
   text	   data	    bss	    dec	    hex	filename
  83356	     28	   8768	  92152	  167f8	evkbimxrt1050_sai_interrupt_transfer_link-to-ram.axf
```

### flash project

The linker gives this information:

```
Memory region         Used Size  Region Size  %age Used
     BOARD_FLASH:       91580 B        64 MB      0.14%
        SRAM_DTC:        8796 B       128 KB      6.71%
        SRAM_ITC:          0 GB       128 KB      0.00%
         SRAM_OC:          0 GB       256 KB      0.00%
     BOARD_SDRAM:          0 GB        32 MB      0.00%
```

`size` conmmand says:

```
   text	   data	    bss	    dec	    hex	filename
  91552	     28	   8768	 100348	  187fc	evkbimxrt1050_sai_interrupt_transfer_flash.axf
```

## memRegion.py

Its primary goal is to extract information about memory regions from the map
file, in order to insert them into the elf file.

It extracts the information and serializes it into JSON. Alternatively it can
print them in human format.

> Why not extract the information from the elf file?<br>
> Because in the elf the information is incomplete, and needs to be interpreted. <br>
>
> Why not extract the information from the linker scripts?<br>
> In linker scripts, memory regions often contain symbols, formulas, or linker
scripts include others. So I preferred to start from the map file that contains
a description of the regions already processed and usable.

### synopsis

```
$ python3 memRegion.py --help
usage: memRegion.py [-h] [--human] mapfile

positional arguments:
  mapfile     input map file

optional arguments:
  -h, --help  show this help message and exit
  --human     print human readable
max@jarvis:~/Dropbox/4202/prog/memLayout$ 
```

### examples

#### human readable

```
$ python3 memRegion.py --human evkbimxrt1050_sai_interrupt_transfer_flash.map
Name             Origin             Length             Attributes
BOARD_FLASH      0x0000000060000000 0x0000000004000000 xr
SRAM_DTC         0x0000000020000000 0x0000000000020000 xrw
SRAM_ITC         0x0000000000000000 0x0000000000020000 xrw
SRAM_OC          0x0000000020200000 0x0000000000040000 xrw
BOARD_SDRAM      0x0000000080000000 0x0000000002000000 xrw

$ python3 memRegion.py --human evkbimxrt1050_sai_interrupt_transfer_link-to-ram.map 
Name             Origin             Length             Attributes
BOARD_FLASH      0x0000000060000000 0x0000000004000000 xr
SRAM_ITC         0x0000000000000000 0x0000000000020000 xrw
SRAM_DTC         0x0000000020000000 0x0000000000020000 xrw
SRAM_OC          0x0000000020200000 0x0000000000040000 xrw
BOARD_SDRAM      0x0000000080000000 0x0000000002000000 xrw
```
This is almost the same format as the memory regions within the map file.

#### JSON output

```
$ python3 memRegion.py evkbimxrt1050_sai_interrupt_transfer_flash.map
{"BOARD_FLASH": {"Origin": 1610612736, "Length": 67108864, "Attributes": "xr"}, "SRAM_DTC": {"Origin": 536870912, "Length": 131072, "Attributes": "xrw"}, "SRAM_ITC": {"Origin": 0, "Length": 131072, "Attributes": "xrw"}, "SRAM_OC": {"Origin": 538968064, "Length": 262144, "Attributes": "xrw"}, "BOARD_SDRAM": {"Origin": 2147483648, "Length": 33554432, "Attributes": "xrw"}}

$ python3 memRegion.py evkbimxrt1050_sai_interrupt_transfer_link-to-ram.map 
{"BOARD_FLASH": {"Origin": 1610612736, "Length": 67108864, "Attributes": "xr"}, "SRAM_ITC": {"Origin": 0, "Length": 131072, "Attributes": "xrw"}, "SRAM_DTC": {"Origin": 536870912, "Length": 131072, "Attributes": "xrw"}, "SRAM_OC": {"Origin": 538968064, "Length": 262144, "Attributes": "xrw"}, "BOARD_SDRAM": {"Origin": 2147483648, "Length": 33554432, "Attributes": "xrw"}}
```
#### embedding JSON into elf

```
$ arm-none-eabi-objcopy --add-section .memory_configuration=<(python3 memRegion.py evkbimxrt1050_sai_interrupt_transfer_flash.map) evkbimxrt1050_sai_interrupt_transfer_flash.axf evkbimxrt1050_sai_interrupt_transfer_flash_and_Region.elf

$ arm-none-eabi-readelf -S evkbimxrt1050_sai_interrupt_transfer_flash_and_Region.elf
There are 30 section headers, starting at offset 0x1db890:

Section Headers:
  [Nr] Name              Type            Addr     Off    Size   ES Flg Lk Inf Al
  [ 0]                   NULL            00000000 000000 000000 00      0   0  0
  [ 1] .boot_hdr         PROGBITS        60000000 010000 002000 00   A  0   0  4
  [ 2] .text             PROGBITS        60002000 012000 0145a0 00  AX  0   0  4
  [ 3] .data             PROGBITS        20000000 030000 00001c 00  WA  0   0  4
  [ 4] .data_RAM2        PROGBITS        00000000 03001c 000000 00   W  0   0  4
  [ 5] .data_RAM3        PROGBITS        20200000 03001c 000000 00   W  0   0  4
  [ 6] .data_RAM4        PROGBITS        80000000 03001c 000000 00   W  0   0  4
  [ 7] .bss              NOBITS          2000001c 01001c 000240 00  WA  0   0  4
  [ 8] .uninit_RESERVED  PROGBITS        20000000 03001c 000000 00   W  0   0  4
  [ 9] .noinit_RAM2      PROGBITS        00000000 03001c 000000 00   W  0   0  4
  [10] .noinit_RAM3      PROGBITS        20200000 03001c 000000 00   W  0   0  4
  [11] .noinit_RAM4      PROGBITS        80000000 03001c 000000 00   W  0   0  4
  [12] .noinit           PROGBITS        2000025c 03001c 000000 00   W  0   0  4
  [13] .heap             NOBITS          2000025c 01001c 001000 00  WA  0   0  4
  [14] .heap2stackfill   NOBITS          2000125c 01001c 001000 00  WA  0   0  1
  [15] .stack            PROGBITS        2001f000 03001c 000000 00   W  0   0  4
  [16] .debug_info       PROGBITS        00000000 03001c 0165b9 00      0   0  1
  [17] .debug_abbrev     PROGBITS        00000000 0465d5 0025bc 00      0   0  1
  [18] .debug_aranges    PROGBITS        00000000 048b91 0010d8 00      0   0  1
  [19] .debug_macro      PROGBITS        00000000 049c69 02a195 00      0   0  1
  [20] .debug_line       PROGBITS        00000000 073dfe 006bdd 00      0   0  1
  [21] .debug_str        PROGBITS        00000000 07a9db 1542bd 01  MS  0   0  1
  [22] .comment          PROGBITS        00000000 1cec98 00007f 01  MS  0   0  1
  [23] .ARM.attributes   ARM_ATTRIBUTES  00000000 1ced17 000035 00      0   0  1
  [24] .debug_ranges     PROGBITS        00000000 1ced4c 000f80 00      0   0  1
  [25] .debug_frame      PROGBITS        00000000 1cfccc 003d10 00      0   0  4
  [26] .memory_configura PROGBITS        00000000 1d39dc 000175 00      0   0  1
  [27] .symtab           SYMTAB          00000000 1d3b54 004ce0 10     28 728  4
  [28] .strtab           STRTAB          00000000 1d8834 002f10 00      0   0  1
  [29] .shstrtab         STRTAB          00000000 1db744 00014b 00      0   0  1
Key to Flags:
  W (write), A (alloc), X (execute), M (merge), S (strings), I (info),
  L (link order), O (extra OS processing required), G (group), T (TLS),
  C (compressed), x (unknown), o (OS specific), E (exclude),
  y (purecode), p (processor specific)
```

> Why embed the JSON of the regions into the elf?<br>
> It's actually not strictly required, as the `memoryLayout.py` tool is
able to draw from both elf and map. However, it is one more option:<br>
> Instead of needing both the elf and the map (often very large and not always
available) you can only transport the elf containing the required information.

"enriched" elf have also been included in the repository.

## memoryLayout.py

Its purpose is to extract and print the information on the layout of the various
memory regions.

### synopsis

```
$ python3 memoryLayout.py --help
usage: memoryLayout.py [--help] [-v] [-ro] [-p] [-dr REG] [-h]
                       elffile [mapfile]

positional arguments:
  elffile               input elf file
  mapfile               input map file (shoud be unused)

optional arguments:
  --help                show this help message and exit
  -v, --verbose         print some message
  -ro, --extract-rodata
                        unbundle .rodata infos
  -p, --percentages     print percentages
  -dr REG, --debug-region REG
                        some debug prints about REG memory region
  -h, --human-readable  print human readable values
```

It tries to extract the information from the elf, in the `.memory_configuration`
section it expects to find the JSON description of the memory regions.
Alternatively it needs the map file

### examples

```
$ python3 memoryLayout.py evkbimxrt1050_sai_interrupt_transfer_link-to-ram_and_Region.elf
Memory region             .text        .data         .bss      LoadMap        Total
     BOARD_FLASH:           0 B          0 B          0 B          0 B          0 B
        SRAM_ITC:       83356 B          0 B          0 B         28 B      83384 B
        SRAM_DTC:           0 B         28 B       8768 B          0 B       8796 B
         SRAM_OC:           0 B          0 B          0 B          0 B          0 B
     BOARD_SDRAM:           0 B          0 B          0 B          0 B          0 B


$ python3 memoryLayout.py -ro evkbimxrt1050_sai_interrupt_transfer_flash.axf evkbimxrt1050_sai_interrupt_transfer_flash.map 
Memory region             .text      .rodata        .data         .bss      LoadMap        Total
     BOARD_FLASH:       83360 B       8192 B          0 B          0 B         28 B      91580 B
        SRAM_DTC:           0 B          0 B         28 B       8768 B          0 B       8796 B
        SRAM_ITC:           0 B          0 B          0 B          0 B          0 B          0 B
         SRAM_OC:           0 B          0 B          0 B          0 B          0 B          0 B
     BOARD_SDRAM:           0 B          0 B          0 B          0 B          0 B          0 B
```

## dissect.py

The purpose of this tool is to retrieve from the `.elf` file the list of all symbols
and associate to them the source or object file that declare them. It can also indicate
the line of the source where the symbol has been declared (only if this information is
present in the `.elf` file) and tries to _guess_ also the `*fill*` gaps.

### synopsis

```
$ python3 dissect.py --help
usage: dissect.py [-h] [-t {normal,csv}] [-o OUT] [-r REG] [-u] [-f] [-l] [-p PREFIX] elffile mapfile

positional arguments:
  elffile               input elf file
  mapfile               input map file

optional arguments:
  -h, --help            show this help message and exit
  -t {normal,csv}, --type {normal,csv}
                        output type (default: normal)
  -o OUT, --out OUT     out file (default: stdout)
  -r REG, --region REG  memory region to dissect (default: all)
  -u, --uniq            filter symbols @address already populated
  -f, --fill            try to guess the *fill* fields
  -l, --noline          remove any line number from files
  -p PREFIX, --prefix PREFIX
                        prefix for nm tool (e.g. arm-none-eabi-, default: "")
  ```

It integrates the information contained in the `.elf` file together with that of the
`.map` file to get the most specific details possible about the symbols.<br>
For this reason it is mandatory to provide this tool with both `.elf` and `.map`.<br>
This tool makes use of system tools such as `grep`, `sed`, `tr`, etc. To get the list
of symbols from `.elf` it uses `nm` possibly by specific architecture (using `--prefix`
parameter). The used `nm` tool is required to be in the `PATH`.<br>
It can produce a human readable output or a csv to be imported by spreadsheets and be
able to filter, search or find the information we are looking for.<br>
It may happen that several symbols have the same address and size (e.g. `__attribute__((alias))`).
Normally all symbols are listed, but this can be misleading when calculating cell sizes.
With the `--uniq` option only one of the symbols is listed.<br>
Due to data types or alignments placed on memory sections, it may happen that there
are "gaps" between various symbols. In the `.map` file they are indicated with `*fill*`.
Using the `--fill` option you ask the tool to try to guess these gaps and list them.

### examples

```
$ python3 dissect.py --type=normal --uniq --prefix=arm-none-eabi- examples/evkbimxrt1050_sai_interrupt_transfer_link-to-ram.axf examples/evkbimxrt1050_sai_interrupt_transfer_link-to-ram.map
          Region  addr(hex)    addr(dec) size(hex)  type                                   symbol path
        SRAM_ITC 0x00000000            0       672     T                             g_pfnVectors /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../startup/startup_mimxrt1052.c:414
        SRAM_ITC 0x000002f0          752        76     T                                 ResetISR /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../startup/startup_mimxrt1052.c:630
        SRAM_ITC 0x0000033c          828        30     T                                data_init /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../startup/startup_mimxrt1052.c:596
        SRAM_ITC 0x0000035a          858        18     T                                 bss_init /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../startup/startup_mimxrt1052.c:605
        SRAM_ITC 0x0000036c          876         2     W                              NMI_Handler /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../startup/startup_mimxrt1052.c:722
[...]
        SRAM_DTC 0x20000120    536871200         4     b                               s_saiTxIsr /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_sai.c:109
        SRAM_DTC 0x20000124    536871204         4     b                               s_saiRxIsr /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_sai.c:111
        SRAM_DTC 0x20000128    536871208       112     b                                reg_cache /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../codec/fsl_wm8960.c:34
        SRAM_DTC 0x20000198    536871320       180     B                                   __Ciob /usr/local/mcuxpressoide-10.3.1_2233/ide/plugins/com.nxp.mcuxpresso.tools.linux_10.3.0.201811011841/tools/bin/../lib/gcc/arm-none-eabi/7.3.1/../../../../arm-none-eabi/lib/thumb/v7e-m/fpv5/hard/libcr_semihost_nf.a(__ciob.o)
        SRAM_DTC 0x2000024c    536871500         4     B                            __end_of_heap /usr/local/mcuxpressoide-10.3.1_2233/ide/plugins/com.nxp.mcuxpresso.tools.linux_10.3.0.201811011841/tools/bin/../lib/gcc/arm-none-eabi/7.3.1/../../../../arm-none-eabi/lib/thumb/v7e-m/fpv5/hard/libcr_c.a(__init_alloc.o)
        SRAM_DTC 0x20000250    536871504         4     B                                  __heaps /usr/local/mcuxpressoide-10.3.1_2233/ide/plugins/com.nxp.mcuxpresso.tools.linux_10.3.0.201811011841/tools/bin/../lib/gcc/arm-none-eabi/7.3.1/../../../../arm-none-eabi/lib/thumb/v7e-m/fpv5/hard/libcr_c.a(__init_alloc.o)
        SRAM_DTC 0x20000254    536871508         4     B                                    errno /usr/local/mcuxpressoide-10.3.1_2233/ide/plugins/com.nxp.mcuxpresso.tools.linux_10.3.0.201811011841/tools/bin/../lib/gcc/arm-none-eabi/7.3.1/../../../../arm-none-eabi/lib/thumb/v7e-m/fpv5/hard/libcr_c.a(errno.o)
        SRAM_DTC 0x20000258    536871512         1     b                               isFinished /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../source_transfer/sai_interrupt_transfer.c:59


python3 dissect.py --type=normal --fill --prefix=arm-none-eabi- examples/evkbimxrt1050_sai_interrupt_transfer_flash.axf examples/evkbimxrt1050_sai_interrupt_transfer_flash.map
          Region  addr(hex)    addr(dec) size(hex)  type                                   symbol path
        SRAM_DTC 0x20000000    536870912         4     D                          SystemCoreClock /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../device/system_MIMXRT1052.c:67
        SRAM_DTC 0x20000004    536870916        24     D                         boardCodecConfig /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../board/board.c:22
        SRAM_DTC 0x2000001c    536870940        28     b                      s_debugConsoleState /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../utilities/fsl_debug_console.c:194
        SRAM_DTC 0x20000038    536870968         4     B                           g_serialHandle /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../utilities/fsl_debug_console.c:195
        SRAM_DTC 0x2000003c    536870972        76     B                                 txHandle /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../source_transfer/sai_interrupt_transfer.c:58
        SRAM_DTC 0x20000088    536871048        24     B                              codecHandle /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../source_transfer/sai_interrupt_transfer.c:61
        SRAM_DTC 0x200000a0    536871072         4     B                               g_xtalFreq /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_clock.c:51
        SRAM_DTC 0x200000a4    536871076         4     B                            g_rtcXtalFreq /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_clock.c:53
        SRAM_DTC 0x200000a8    536871080         4     b                         s_lpi2cMasterIsr /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_lpi2c.c:133
        SRAM_DTC 0x200000ac    536871084        20     b                      s_lpi2cMasterHandle /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_lpi2c.c:136
[...]
     BOARD_FLASH 0x6001558c   1610700172        36     t                            s_lpuartBases /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_lpuart.c:76
     BOARD_FLASH 0x600155b0   1610700208        18     t                            s_lpuartClock /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_lpuart.c:88
     BOARD_FLASH 0x600155c2   1610700226      1022                                         *fill* 
     BOARD_FLASH 0x600159c0   1610701248        16     t                               s_saiBases /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_sai.c:98
     BOARD_FLASH 0x600159d0   1610701264         8     t                               s_saiTxIRQ /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_sai.c:102
     BOARD_FLASH 0x600159d8   1610701272         8     t                               s_saiClock /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../drivers/fsl_sai.c:106
     BOARD_FLASH 0x600159e0   1610701280        36     t                      s_LpuartAdapterBase /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../component/uart/lpuart_adapter.c:63
     BOARD_FLASH 0x60015a04   1610701316      2524                                         *fill* 
     BOARD_FLASH 0x600163e0   1610703840       112     t                               wm8960_reg /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../codec/fsl_wm8960.c:27
     BOARD_FLASH 0x60016450   1610703952       160                                         *fill* 
     BOARD_FLASH 0x600164f0   1610704112         8     T          armPllConfig_BOARD_BootClockRUN /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../board/clock_config.c:142
     BOARD_FLASH 0x600164f8   1610704120        20     T          sysPllConfig_BOARD_BootClockRUN /home/max/Lavori/4202/wksp_test1/evkbimxrt1050_sai_interrupt_transfer/Debug/../board/clock_config.c:146
     BOARD_FLASH 0x6001650c   1610704140        40                                         *fill* 
     BOARD_FLASH 0x60016534   1610704180         4     T                       __num_Ciob_streams /usr/local/mcuxpressoide-10.3.1_2233/ide/plugins/com.nxp.mcuxpresso.tools.linux_10.3.0.201811011841/tools/bin/../lib/gcc/arm-none-eabi/7.3.1/../../../../arm-none-eabi/lib/thumb/v7e-m/fpv5/hard/libcr_semihost_nf.a(__ciob.o)
```

### note on the size of the memory sections

It may happen that if you add up the size of the symbols contained in a specific memory
region, the result may be a different number than the one indicated by the `memoryLayout.py` tool.

For example:

```
$ python3 dissect.py --type=normal --fill --uniq --region=BOARD_FLASH --prefix=arm-none-eabi- examples/evkbimxrt1050_sai_interrupt_transfer_flash.axf examples/evkbimxrt1050_sai_interrupt_transfer_flash.map | awk '{s+=$4} END {print s}'
91448
```

but `memoryLayout.py` says `91552` (.text + .rodata)

and again

```
$ python3 dissect.py --type=normal --fill --uniq --region=SRAM_DTC --prefix=arm-none-eabi- examples/evkbimxrt1050_sai_interrupt_transfer_link-to-ram.axf examples/evkbimxrt1050_sai_interrupt_transfer_link-to-ram.map | awk '{s+=$4} END {print s}'
601
```
but `memoryLayout.py` says `8796` (.data + .bss)

This is because of some factors: `*fill*` gaps at the end of a region (to maintain alignment);
directives given in the linker script such as reserving space for heap and stack, that don't
correspond to any symbol.<br>
In all the cases I analyzed, I was able to give an explanation.<br>
If you find cases that you can't explain, please let me know, sending me also `.elf` and `.map`
and indicating the exact version of toolchain you used.

## regions.py

This tool simply lists the names of the memory regions. It can be useful in shell scripts.

### synopsis

```
$ python3 regions.py --helpusage: regions.py [-h] elffile [mapfile]

positional arguments:
  elffile     input elf file
  mapfile     input map file

optional arguments:
  -h, --help  show this help message and exit
```

### examples

```
$ python3 regions.py examples/evkbimxrt1050_sai_interrupt_transfer_link-to-ram.axf examples/evkbimxrt1050_sai_interrupt_transfer_link-to-ram.map 
BOARD_FLASH
SRAM_ITC
SRAM_DTC
SRAM_OC
BOARD_SDRAM
```

## Further readings and developments

These tools were inspired by reading this post:

[Tracking Firmware Code Size](https://interrupt.memfault.com/blog/code-size-deltas)

my hope is that someone (or myself) can take the work forward to create a tool
that traces the memory occupation along the git commits (maybe even graphically)