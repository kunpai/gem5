# Microbenchmark kernels. Signature: fn(a0=n iterations, a1=base, a2=stride, a3=mask)
# All 4-byte instructions so both simulators see the same fetch stream.
    .section .text.kernels, "ax"
    .option norvc

.macro KERNEL name
    .balign 64
    .globl \name
\name:
.endm

# --- integer execution -------------------------------------------------
KERNEL k_alu_dep                 # 8 dependent adds per iteration
    li t0, 0
1:  .rept 8
    addi t0, t0, 1
    .endr
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_alu_indep               # 8 independent adds per iteration
    li t0, 0; li t1, 0; li t2, 0; li t3, 0
    li t4, 0; li t5, 0; li t6, 0; li a4, 0
1:  addi t0, t0, 1
    addi t1, t1, 1
    addi t2, t2, 1
    addi t3, t3, 1
    addi t4, t4, 1
    addi t5, t5, 1
    addi t6, t6, 1
    addi a4, a4, 1
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_mul_dep                 # 4 dependent multiplies per iteration
    li t0, 3
    li t1, 5
1:  .rept 4
    mul t0, t0, t1
    .endr
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_div_dep                 # 2 dependent 64-bit divides per iteration
    li t0, -1
    srli t0, t0, 1               # large dividend
    li t1, 3
    mv t3, t0
1:  div t2, t0, t1
    xor t0, t2, t3               # keep dividend large, dependent on quotient
    div t2, t0, t1
    xor t0, t2, t3
    addi a0, a0, -1
    bnez a0, 1b
    ret

# --- control flow ------------------------------------------------------
KERNEL k_br_loop                 # minimal taken-branch loop
1:  addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_br_random               # data-dependent branch on xorshift bit (~50% taken)
    li t0, 0x2545F4914F6CDD1D
    li t4, 0
1:  slli t1, t0, 13
    xor  t0, t0, t1
    srli t1, t0, 7
    xor  t0, t0, t1
    slli t1, t0, 17
    xor  t0, t0, t1
    andi t2, t0, 1
    beqz t2, 2f
    addi t4, t4, 1
    addi t4, t4, 1
2:  addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_br_pattern              # branch with period-7 pattern T T N T N N N
    li t0, 0                     # phase
    li t3, 7
    li t5, 0b0001011             # bit i = taken at phase i
    li t4, 0
1:  srl  t1, t5, t0
    andi t1, t1, 1
    beqz t1, 2f
    addi t4, t4, 1
2:  addi t0, t0, 1
    bne  t0, t3, 3f
    li   t0, 0
3:  addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_call_ret                # call/return pairs, depth 2
    mv t6, ra
    li t4, 0
1:  jal ra, 5f
    addi a0, a0, -1
    bnez a0, 1b
    mv ra, t6
    ret
5:  mv t5, ra
    jal ra, 6f
    mv ra, t5
    ret
6:  addi t4, t4, 1
    ret

KERNEL k_indirect                # jalr alternating between two targets
    la t1, 4f
    la t2, 5f
    li t4, 0
1:  andi t3, a0, 1
    mv t0, t1
    beqz t3, 2f                  # (this select branch alternates too)
    mv t0, t2
2:  jr t0
    .balign 16
4:  addi t4, t4, 1
    j 6f
    .balign 16
5:  addi t4, t4, 2
6:  addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_jumpchain               # 1024 direct jumps, one per 64-byte line (64 KiB of code)
1:  .rept 1024
    j 7f
    .balign 64
7:
    .endr
    addi a0, a0, -1
    bnez a0, 1b
    ret

# --- memory ------------------------------------------------------------
KERNEL k_load_dep                # dependent loads: next address depends on loaded value (memory is 0)
    li t2, 0
    mv t3, a1
1:  ld  t1, 0(t3)
    add t2, t2, t1
    add t2, t2, a2
    and t2, t2, a3
    add t3, a1, t2
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_load_indep              # independent loads: address does not depend on data
    li t2, 0
    li t4, 0
    mv t3, a1
1:  ld  t1, 0(t3)
    add t4, t4, t1
    add t2, t2, a2
    and t2, t2, a3
    add t3, a1, t2
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_store_load              # store then load same address, value carried through memory
    li t0, 0
1:  sd  t0, 0(a1)
    ld  t1, 0(a1)
    addi t0, t1, 1
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_store_stream            # independent stores walking a region
    li t2, 0
    mv t3, a1
1:  sd  a0, 0(t3)
    add t2, t2, a2
    and t2, t2, a3
    add t3, a1, t2
    addi a0, a0, -1
    bnez a0, 1b
    ret

# --- floating point ----------------------------------------------------
KERNEL k_fadd_dep                # 4 dependent double adds per iteration
    fmv.d.x f0, x0
    li t0, 0x3FF0000000000000    # 1.0
    fmv.d.x f1, t0
1:  .rept 4
    fadd.d f0, f0, f1
    .endr
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_fmul_dep                # 4 dependent double multiplies per iteration
    li t0, 0x3FF0000000000000
    fmv.d.x f0, t0
    li t0, 0x3FF0000000000001    # just above 1.0
    fmv.d.x f1, t0
1:  .rept 4
    fmul.d f0, f0, f1
    .endr
    addi a0, a0, -1
    bnez a0, 1b
    ret

KERNEL k_fdiv_dep                # 2 dependent double divides per iteration
    li t0, 0x4059000000000000    # 100.0
    fmv.d.x f0, t0
    li t0, 0x3FF0000000000001
    fmv.d.x f1, t0
1:  fdiv.d f0, f0, f1
    fdiv.d f0, f0, f1
    addi a0, a0, -1
    bnez a0, 1b
    ret
