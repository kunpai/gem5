OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS {
  . = 0x80000000;
  .text.init : { *(.text.init) }
  . = ALIGN(4096);
  .text.kernels : { *(.text.kernels) *workloads.o(.rodata .rodata.* .srodata* .sdata* .data*) }     /* kernels first: identical addresses in both builds */
  . = ALIGN(4096);
  .text : { *(.text .text.*) }
  .rodata : { *(.rodata .rodata.* .srodata*) }
  .data : { *(.data .data.* .sdata*) }
  .bss : { *(.bss .bss.* .sbss* COMMON) }
  . = 0x80400000;
  _stack_top = .;
}
