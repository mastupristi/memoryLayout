all: main.elf

CFLAGS = \
	-std=gnu11 \
	-mcpu=cortex-m7 \
	-mthumb \
	-specs=nano.specs \
	-O0 \
	-Wall \
	-ffunction-sections \
	-fdata-sections \
	-c \
	-Werror

LDFLGS =  \
	-mcpu=cortex-m7 \
	-mthumb \
	-specs=nano.specs \
	-Wl,--gc-sections \
	-Wl,--print-memory-usage

LD_SCRIPT = STM32F410RBTx_FLASH.ld

CC = arm-none-eabi-gcc

main.elf: main.o
	$(CC) $(LDFLGS) -T$(LD_SCRIPT) -Wl,--cref,-Map=$(@:.elf=.map) -o $@ $^

main.o: main.c
	$(CC) $(CFLAGS) -o $@ $< 

.PHONY: clean

clean:
	rm *.o *.elf *.map
