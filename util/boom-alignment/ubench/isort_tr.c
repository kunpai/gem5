/* insertion sort with the benchmark calling convention fn(n, arena) for the trace run */
typedef unsigned long u64; typedef unsigned int u32; typedef long i64;
__attribute__((section(".text.kernels"), noinline))
void w_isort_tr(u64 n, u64 arena, u64 x, u64 y) {
  u32 *a = (u32 *)arena, s = 4242; (void)x; (void)y;
  for (u64 i = 0; i < n; i++) { s = s * 1664525u + 1013904223u; a[i] = (s >> 8) & 0xffff; }
  for (u64 i = 1; i < n; i++) { u32 v = a[i]; i64 j = (i64)i - 1; while (j >= 0 && a[j] > v) { a[j + 1] = a[j]; j--; } a[j + 1] = v; }
}
