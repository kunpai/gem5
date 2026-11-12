CC = riscv64-unknown-elf-gcc
CFLAGS = -O2 -march=rv64gc -mabi=lp64d -mcmodel=medany -ffreestanding -nostdlib -nostartfiles -static -fno-builtin -Wall
all: ubench_boom.elf ubench_boom.bin ubench_gem5.elf
ubench_boom.elf: start.S kernels.S main.c link.ld
	$(CC) $(CFLAGS) -T link.ld -o $@ start.S kernels.S main.c
ubench_gem5.elf: start.S kernels.S main.c link.ld
	$(CC) $(CFLAGS) -DPLAT_GEM5 -T link.ld -o $@ start.S kernels.S main.c
%.bin: %.elf
	riscv64-unknown-elf-objcopy -O binary $< $@

all2: ubench2_boom.bin ubench2_gem5.elf
ubench2_boom.elf: start.S kernels2.S main2.c link.ld
	$(CC) $(CFLAGS) -T link.ld -o $@ start.S kernels2.S main2.c
ubench2_gem5.elf: start.S kernels2.S main2.c link.ld
	$(CC) $(CFLAGS) -DPLAT_GEM5 -T link.ld -o $@ start.S kernels2.S main2.c
