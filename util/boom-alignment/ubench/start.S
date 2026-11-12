    .section .text.init
    .option norvc
    .globl _start
_start:
    li   t0, 0x6000            # mstatus.FS = dirty, enable FP
    csrs mstatus, t0
    la   sp, _stack_top
    la   t0, trap
    csrw mtvec, t0
    call main
1:  j 1b
    .balign 4
trap:                          # any unexpected trap: report 'T' via platform and stop
    call plat_trap
1:  j 1b

#ifdef PLAT_GEM5
    .balign 16
    .globl sh_call            # a0 = semihosting op, a1 = arg
sh_call:
    slli x0, x0, 0x1f
    ebreak
    srai x0, x0, 7
    ret
    .globl m5_reset_stats
m5_reset_stats:
    li a0, 0
    li a1, 0
    .long 0x8000007b
    ret
    .globl m5_dump_stats
m5_dump_stats:
    li a0, 0
    li a1, 0
    .long 0x8200007b
    ret
    .globl m5_exit
m5_exit:
    li a0, 0
    .long 0x4200007b
    ret
#endif
