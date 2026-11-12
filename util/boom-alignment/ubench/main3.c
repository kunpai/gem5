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

typedef u64 (*wfn)(u64 *arena, u64 n);
#define WL(x) extern u64 x(u64 *, u64);
WL(w_qsort) WL(w_matmul) WL(w_crc) WL(w_list) WL(w_bsearch) WL(w_sieve) WL(w_fib) WL(w_hash)
WL(w_str) WL(w_fp) WL(w_gcd) WL(w_isort) WL(w_stencil) WL(w_bits) WL(w_interp)
struct wl { const char *name; wfn fn; u64 n; };
static const struct wl B[] = {
  {"qsort", w_qsort, 1500}, {"matmul", w_matmul, 20}, {"crc", w_crc, 1500}, {"list", w_list, 3000},
  {"bsearch", w_bsearch, 1500}, {"sieve", w_sieve, 12000}, {"fib", w_fib, 17}, {"hash", w_hash, 2000},
  {"str", w_str, 3}, {"fp", w_fp, 2500}, {"gcd", w_gcd, 500}, {"isort", w_isort, 250},
  {"stencil", w_stencil, 40000}, {"bits", w_bits, 1500}, {"interp", w_interp, 12000},
};
#define ARENA ((u64 *)0x81400000UL)
static void put_hex(u64 v) { char b[20]; int i = 19; b[i] = 0; do { b[--i] = "0123456789abcdef"[v & 15]; v >>= 4; } while (v); plat_puts(&b[i]); }

int main(void) {
  plat_init();
  plat_puts("BENCH name cycles instret\n");
  for (unsigned i = 0; i < sizeof(B) / sizeof(B[0]); i++) {
    const struct wl *b = &B[i];
    for (int pass = 0; pass < 2; pass++) {          /* pass 0 = cold caches, pass 1 = warm */
      ROI_BEGIN();
      u64 c0 = rd_cycle(), i0 = rd_instret();
      u64 r = b->fn(ARENA + i * 0x40000, b->n);
      u64 c1 = rd_cycle(), i1 = rd_instret();
      ROI_END();
      plat_puts("RES "); plat_puts(b->name); plat_puts(pass ? "_warm " : "_cold ");
      put_dec(c1 - c0); plat_puts(" "); put_dec(i1 - i0); plat_puts(" chk="); put_hex(r); plat_puts("\n");
    }
  }
  plat_puts("DONE\n");
  plat_done();
  for (;;);
}
