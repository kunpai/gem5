/* Held-out workloads: ordinary compiled C (rv64gc, compressed instructions allowed).
   None of these were used to fit any gem5 parameter. Each returns a checksum. */
typedef unsigned long u64; typedef unsigned int u32; typedef unsigned char u8; typedef long i64;
#define W __attribute__((section(".text.kernels"), noinline))

W void *memset(void *d, int c, u64 n) { u8 *p = d; while (n--) *p++ = (u8)c; return d; }
W void *memcpy(void *d, const void *s, u64 n) { u8 *p = d; const u8 *q = s; while (n--) *p++ = *q++; return d; }
static inline u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s >> 8; }

/* 1. quicksort (recursive, data-dependent branches) */
W static void qs(u32 *a, i64 lo, i64 hi) {
  while (lo < hi) {
    u32 p = a[(lo + hi) >> 1]; i64 i = lo, j = hi;
    while (i <= j) { while (a[i] < p) i++; while (a[j] > p) j--; if (i <= j) { u32 t = a[i]; a[i] = a[j]; a[j] = t; i++; j--; } }
    if (j - lo < hi - i) { qs(a, lo, j); lo = i; } else { qs(a, i, hi); hi = j; }
  }
}
W u64 w_qsort(u64 *arena, u64 n) {
  u32 *a = (u32 *)arena, s = 12345; for (u64 i = 0; i < n; i++) a[i] = lcg(&s);
  qs(a, 0, (i64)n - 1); u64 c = 0; for (u64 i = 0; i < n; i += 7) c = c * 31 + a[i]; return c;
}
/* 2. dense double matrix multiply */
W u64 w_matmul(u64 *arena, u64 n) {
  double *A = (double *)arena, *B = A + n * n, *C = B + n * n;
  for (u64 i = 0; i < n * n; i++) { A[i] = (double)(i % 13) * 0.5; B[i] = (double)(i % 7) + 1.0; }
  for (u64 i = 0; i < n; i++) for (u64 j = 0; j < n; j++) { double s = 0; for (u64 k = 0; k < n; k++) s += A[i * n + k] * B[k * n + j]; C[i * n + j] = s; }
  double t = 0; for (u64 i = 0; i < n * n; i++) t += C[i]; return (u64)t;
}
/* 3. bitwise CRC-32 */
W u64 w_crc(u64 *arena, u64 n) {
  u8 *b = (u8 *)arena; u32 s = 7; for (u64 i = 0; i < n; i++) b[i] = (u8)lcg(&s);
  u32 c = 0xffffffffu; for (u64 i = 0; i < n; i++) { c ^= b[i]; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xedb88320u & -(c & 1)); }
  return ~c;
}
/* 4. linked-list traversal over shuffled nodes */
struct node { struct node *next; u64 val; u64 pad[2]; };
W u64 w_list(u64 *arena, u64 n) {
  struct node *nd = (struct node *)arena; u32 *perm = (u32 *)(nd + n), s = 99;
  for (u64 i = 0; i < n; i++) perm[i] = (u32)i;
  for (u64 i = n - 1; i > 0; i--) { u64 j = lcg(&s) % (i + 1); u32 t = perm[i]; perm[i] = perm[j]; perm[j] = t; }
  for (u64 i = 0; i < n; i++) { nd[perm[i]].val = i; nd[perm[i]].next = (i + 1 < n) ? &nd[perm[i + 1]] : 0; }
  u64 c = 0; for (int r = 0; r < 3; r++) for (struct node *p = &nd[perm[0]]; p; p = p->next) c += p->val ^ (u64)r; return c;
}
/* 5. binary search */
W u64 w_bsearch(u64 *arena, u64 n) {
  u32 *a = (u32 *)arena, s = 5; for (u64 i = 0; i < 4096; i++) a[i] = (u32)(i * 3);
  u64 c = 0; for (u64 q = 0; q < n; q++) { u32 key = lcg(&s) % 12288; i64 lo = 0, hi = 4095;
    while (lo <= hi) { i64 m = (lo + hi) >> 1; if (a[m] == key) { c += (u64)m; break; } if (a[m] < key) lo = m + 1; else hi = m - 1; } }
  return c;
}
/* 6. sieve of Eratosthenes */
W u64 w_sieve(u64 *arena, u64 n) {
  u8 *f = (u8 *)arena; for (u64 i = 0; i < n; i++) f[i] = 1;
  u64 c = 0; for (u64 i = 2; i < n; i++) if (f[i]) { c++; for (u64 j = i * 2; j < n; j += i) f[j] = 0; } return c;
}
/* 7. recursive fibonacci (calls and returns) */
W static u64 fib(u64 n) { return n < 2 ? n : fib(n - 1) + fib(n - 2); }
W u64 w_fib(u64 *arena, u64 n) { (void)arena; return fib(n); }
/* 8. open-addressing hash table */
W u64 w_hash(u64 *arena, u64 n) {
  u64 *t = arena; for (u64 i = 0; i < 4096; i++) t[i] = 0; u32 s = 77; u64 c = 0;
  for (u64 i = 0; i < n; i++) { u64 k = lcg(&s) | 1, h = (k * 0x9E3779B97F4A7C15UL) >> 52; while (t[h] && t[h] != k) h = (h + 1) & 4095; t[h] = k; }
  s = 77; for (u64 i = 0; i < n; i++) { u64 k = lcg(&s) | 1, h = (k * 0x9E3779B97F4A7C15UL) >> 52; while (t[h] != k) h = (h + 1) & 4095; c += h; }
  return c;
}
/* 9. byte-string operations */
W u64 w_str(u64 *arena, u64 n) {
  u8 *a = (u8 *)arena, *b = a + 8192; u32 s = 3; for (u64 i = 0; i < 4096; i++) a[i] = (u8)('a' + lcg(&s) % 26); a[4095] = 0;
  u64 c = 0; for (u64 r = 0; r < n; r++) { memcpy(b, a, 4096); u64 l = 0; while (b[l]) l++; c += l; b[(r * 37) % 4000] ^= 1; u64 i = 0; while (a[i] == b[i] && a[i]) i++; c += i; }
  return c;
}
/* 10. floating point: polynomial evaluation with a divide per element */
W u64 w_fp(u64 *arena, u64 n) {
  double *x = (double *)arena, acc = 0; for (u64 i = 0; i < n; i++) x[i] = 0.001 * (double)(i + 1);
  for (u64 i = 0; i < n; i++) { double v = x[i], p = ((((1.5 * v + 0.25) * v - 3.0) * v + 0.5) * v + 2.0); acc += p / (1.0 + v * v); }
  return (u64)(acc * 1000.0);
}
/* 11. Euclid's gcd with remainder (operand-dependent divides) */
W u64 w_gcd(u64 *arena, u64 n) {
  (void)arena; u32 s = 1234; u64 c = 0;
  for (u64 i = 0; i < n; i++) { u64 a = ((u64)lcg(&s) << 20) | lcg(&s), b = lcg(&s) | 1; while (b) { u64 t = a % b; a = b; b = t; } c += a; }
  return c;
}
/* 12. insertion sort */
W u64 w_isort(u64 *arena, u64 n) {
  u32 *a = (u32 *)arena, s = 4242; for (u64 i = 0; i < n; i++) a[i] = lcg(&s) & 0xffff;
  for (u64 i = 1; i < n; i++) { u32 v = a[i]; i64 j = (i64)i - 1; while (j >= 0 && a[j] > v) { a[j + 1] = a[j]; j--; } a[j + 1] = v; }
  u64 c = 0; for (u64 i = 0; i < n; i += 3) c = c * 17 + a[i]; return c;
}
/* 13. 1-D stencil over an array larger than L1 and comparable to L2 */
W u64 w_stencil(u64 *arena, u64 n) {
  u32 *a = (u32 *)arena, *b = a + n; for (u64 i = 0; i < n; i++) a[i] = (u32)(i * 2654435761u);
  for (int r = 0; r < 2; r++) { for (u64 i = 1; i + 1 < n; i++) b[i] = (a[i - 1] + 2 * a[i] + a[i + 1]) >> 2; u32 *t = a; a = b; b = t; }
  u64 c = 0; for (u64 i = 0; i < n; i += 64) c += a[i]; return c;
}
/* 14. bit manipulation */
W u64 w_bits(u64 *arena, u64 n) {
  (void)arena; u64 x = 0x123456789abcdefUL, c = 0;
  for (u64 i = 0; i < n; i++) { u64 v = x, p = 0; while (v) { v &= v - 1; p++; } c += p; x = (x << 7 | x >> 57) ^ (i * 0x9E3779B97F4A7C15UL); }
  return c;
}
/* 15. bytecode interpreter (switch dispatch through a jump table) */
W u64 w_interp(u64 *arena, u64 n) {
  u8 *code = (u8 *)arena; u32 s = 31; for (u64 i = 0; i < 256; i++) code[i] = (u8)(lcg(&s) % 8);
  u64 acc = 1, reg = 3, pc = 0;
  for (u64 i = 0; i < n; i++) {
    switch (code[pc]) {
      case 0: acc += reg; break;        case 1: acc ^= reg << 3; break;
      case 2: reg = reg * 5 + 1; break; case 3: acc -= reg >> 1; break;
      case 4: reg ^= acc; break;        case 5: acc = acc * 3; break;
      case 6: reg += 7; break;          default: acc += pc; break;
    }
    pc = (pc + 1) & 255;
  }
  return acc ^ reg;
}
