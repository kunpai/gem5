# Validation kernels for the two gem5 patches (divider latency, store-to-load forwarding).
    .section .text.kernels, "ax"
    .option norvc
.macro KERNEL name
    .balign 64
    .globl \name
\name:
.endm

# fn(a0=n, a1=dividend, a2=divisor): one dependent divide per iteration with fixed operands.
# t3 = a1 ^ op(a1,a2), so t0 = op(t0,a2) ^ t3 returns to a1 every iteration.
.macro DIVK name, op
KERNEL \name
    \op  t2, a1, a2
    xor  t3, a1, t2
    mv   t0, a1
1:  \op  t2, t0, a2
    xor  t0, t2, t3
    addi a0, a0, -1
    bnez a0, 1b
    ret
.endm
DIVK k_div,  div
DIVK k_divu, divu
DIVK k_rem,  rem
DIVK k_remu, remu
DIVK k_divw, divw

# store-to-load forwarding variants, fn(a0=n, a1=addr)
KERNEL k_sl_chain2               # forwarded load feeds two adds before the next store
    li t0, 0
1:  sd  t0, 0(a1)
    ld  t1, 0(a1)
    addi t1, t1, 1
    addi t0, t1, 1
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_sl_indep                # forwarded load is not on the loop-carried path
    li t4, 0
1:  sd  a0, 0(a1)
    ld  t1, 0(a1)
    add t4, t4, t1
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_sl_word                 # 32-bit store and load
    li t0, 0
1:  sw  t0, 0(a1)
    lw  t1, 0(a1)
    addi t0, t1, 1
    addi a0, a0, -1
    bnez a0, 1b
    ret
