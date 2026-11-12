typedef unsigned long u64;
typedef void (*kfn)(u64 n, u64 base, u64 stride, u64 mask);
#define K(x) extern void x(u64, u64, u64, u64);
K(k_alu_dep) K(k_alu_indep) K(k_mul_dep) K(k_div_dep) K(k_br_loop) K(k_br_random) K(k_br_pattern)
K(k_call_ret) K(k_indirect) K(k_jumpchain) K(k_load_dep) K(k_load_indep) K(k_store_load)
K(k_store_stream) K(k_fadd_dep) K(k_fmul_dep) K(k_fdiv_dep)

/* ---- platform layer: only this part differs between the two builds ---- */
#ifdef PLAT_GEM5
extern void sh_call(long op, const void *arg);
extern void m5_reset_stats(void), m5_dump_stats(void), m5_exit(void);
static void plat_init(void) {}
static void plat_puts(const char *s) { sh_call(4, s); }          /* SYS_WRITE0 */
static void plat_done(void) { m5_exit(); }
#define ROI_BEGIN() m5_reset_stats()
#define ROI_END() m5_dump_stats()
#else
#define UART ((volatile unsigned int *)0x10000000UL)
static void plat_init(void) { UART[4] = 0; UART[2] = 1; UART[3] = 1; }
static void plat_putc(char c) { while ((int)UART[0] < 0); UART[0] = (unsigned char)c; }
static void plat_puts(const char *s) { while (*s) plat_putc(*s++); }
static void plat_done(void) { plat_putc(4); }
#ifdef PROBE
#define ROI_BEGIN() plat_putc(1)
#define ROI_END() plat_putc(2)
#else
#define ROI_BEGIN()
#define ROI_END()
#endif
#endif
void plat_trap(void) { plat_puts("\nTRAP\n"); plat_done(); for (;;); }

static inline u64 rd_cycle(void) { u64 v; __asm__ volatile("csrr %0, mcycle" : "=r"(v)); return v; }
static inline u64 rd_instret(void) { u64 v; __asm__ volatile("csrr %0, minstret" : "=r"(v)); return v; }

static void put_dec(u64 v) {
  char b[24]; int i = 23; b[i] = 0;
  do { b[--i] = '0' + v % 10; v /= 10; } while (v);
  plat_puts(&b[i]);
}

#define L1REG 0x81000000UL   /* 4 KiB region: fits L1D */
#define L2REG 0x81100000UL   /* 128 KiB region: misses L1D (16 KiB), fits L2 (512 KiB) */
#define MEMA  0x84000000UL   /* untouched DRAM regions, one per run so every access misses L2 */
#define MEMB  0x88000000UL
#define MEMC  0x8a000000UL
#define STK   0x81200000UL

struct bench { const char *name; kfn fn; u64 wn, n, base, stride, mask; };
#define K4(x) extern void x(u64, u64, u64, u64);
K4(k_sl_chain2) K4(k_sl_indep) K4(w_isort_tr) K4(k_copy)
static const struct bench B[] = {
  /* short traced runs: warm-up first, then a few dozen traced iterations */
  {"store_load", k_store_load, 300, 40, STK, 0, 0},
  {"sl_chain2",  k_sl_chain2,  300, 40, STK, 0, 0},
  {"sl_indep",   k_sl_indep,   300, 40, STK, 0, 0},
  {"call_ret",   k_call_ret,   600, 40, 0, 0, 0},
  {"br_pattern", k_br_pattern, 4000, 56, 0, 0, 0},
  {"mul_dep",    k_mul_dep,    200, 20, 0, 0, 0},
  {"load_dep_l1",k_load_dep,   1000, 40, L1REG, 72, 0xfff},
  {"alu_indep",  k_alu_indep,  200, 30, 0, 0, 0},
  {"isort",      w_isort_tr,   40, 40, 0x81400000UL, 0, 0},
  /* memory side: all of these miss L1 and hit L2 after the warm-up passes */
  {"load_indep_l2", k_load_indep, 4096, 64, L2REG, 1088, 0x1ffff},
  {"load_dep_l2",   k_load_dep,   4096, 40, L2REG, 1088, 0x1ffff},
  {"store_l2",      k_store_stream, 4096, 64, L2REG, 1088, 0x1ffff},
  {"copy_l2",       k_copy,       4096, 64, 0x81300000UL, 64, 0xffff},
};

int main(void) {
  plat_init();
  plat_puts("BENCH name cycles instret\n");
  for (unsigned i = 0; i < sizeof(B) / sizeof(B[0]); i++) {
    const struct bench *b = &B[i];
    if (b->wn) b->fn(b->wn, b->base, b->stride, b->mask);   /* warm caches and predictors */
    ROI_BEGIN();
    u64 c0 = rd_cycle(), i0 = rd_instret();
    b->fn(b->n, b->base, b->stride, b->mask);
    u64 c1 = rd_cycle(), i1 = rd_instret();
    ROI_END();
    plat_puts("RES "); plat_puts(b->name); plat_puts(" ");
    put_dec(c1 - c0); plat_puts(" "); put_dec(i1 - i0); plat_puts("\n");
  }
  plat_puts("DONE\n");
  plat_done();
  for (;;);
}
