# Memory Layout

This project aims to extract more detailed information about the memory layout
of an elf file.

What we want is to know how the various memory regions are divided between
`.text` (code), `.data` (initialized data), `.bss` (uninitialized data).
Eventually also dissect further `.text` to highlight also `.rodata` (constant
data).

Using the tools available in the binutils, you can't dissect that deep.


## Examples

I started with SDK 2.5.1 for NXP i.MX RT1050. I took the example
`evkbimxrt1050_sai_interrupt_transfer` configured in two different ways:
- link-to-ram project
- flash project

Nel repositorio ho aggiunto anche i file elf (con estensione `.axf`)  e i file map:

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

## Further readings and developments

these tools were inspired by reading this post:

[Tracking Firmware Code Size](https://interrupt.memfault.com/blog/code-size-deltas)

my hope is that someone (or myself) can take the work forward to create a tool
that traces the memory occupation along the git commits (maybe even graphically)