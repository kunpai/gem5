#include "VTestHarness.h"
#include "verilated.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  unsigned long long maxc = 50000000ULL;
  for (int i = 1; i < argc; i++) if (!strncmp(argv[i], "+max=", 5)) maxc = strtoull(argv[i] + 5, 0, 10);
  VTestHarness* top = new VTestHarness;
  unsigned long long c = 0;
  top->reset = 1; top->clock = 0;
  for (int i = 0; i < 100; i++) { top->clock = !top->clock; top->eval(); }
  top->reset = 0;
  while (!Verilated::gotFinish() && c < maxc) {
    top->clock = 1; top->eval();
    top->clock = 0; top->eval();
    c++;
  }
  fflush(stdout);
  fprintf(stderr, "\n[harness] %s after %llu cycles\n", Verilated::gotFinish() ? "finished" : "TIMEOUT", c);
  top->final();
  return Verilated::gotFinish() ? 0 : 2;
}
