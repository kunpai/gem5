# Memory-side trace kernels.
    .section .text.kernels, "ax"
    .option norvc
# fn(a0=n, a1=src base, a2=stride, a3=mask): load a line from src, store it to dst = src + 0x40000
    .balign 64
    .globl k_copy
k_copy:
    li t2, 0
    li t5, 0x40000
    mv t3, a1
1:  ld  t1, 0(t3)
    add t4, t3, t5
    sd  t1, 0(t4)
    add t2, t2, a2
    and t2, t2, a3
    add t3, a1, t2
    addi a0, a0, -1
    bnez a0, 1b
    ret
