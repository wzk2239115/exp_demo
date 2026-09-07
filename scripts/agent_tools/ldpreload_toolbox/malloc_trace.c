/* malloc_trace.c — LD_PRELOAD malloc/free tracing; sidesteps ptrace restrictions.

Design notes (avoiding last round's fprintf recursion crash):
  - Emit via write(2) directly; never printf/fprintf (they call malloc internally -> recursive segfault)
  - Reentrancy guard: __thread flag prevents the hook from re-triggering itself
  - Records size/address by default; env-controlled (MTRACE=1 full, MTRACE_BACKTRACE=1 with stack)

Build: gcc -shared -fPIC -o malloc_trace.so malloc_trace.c -ldl -rdynamic
Usage:
  LD_PRELOAD=/workspace/tools/ldpreload_toolbox/malloc_trace.so MTRACE=1 ./vuln
  LD_PRELOAD=.../malloc_trace.so MTRACE_BACKTRACE=1 ./vuln < poc   # with stack
  LD_PRELOAD=.../malloc_trace.so MTRACE_FILTER=128 ./vuln          # watch only 128-byte chunks
*/
#define _GNU_SOURCE
#include <dlfcn.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <execinfo.h>

static void* (*real_malloc)(size_t) = NULL;
static void  (*real_free)(void*) = NULL;
static void* (*real_calloc)(size_t, size_t) = NULL;
static void* (*real_realloc)(void*, size_t) = NULL;

static __thread int in_hook = 0;        /* reentrancy guard */
static int trace_on = -1, bt_on = -1, filter_sz = 0;

static void init_real(void) {
    real_malloc  = dlsym(RTLD_NEXT, "malloc");
    real_calloc = dlsym(RTLD_NEXT, "calloc");
    real_realloc= dlsym(RTLD_NEXT, "realloc");
    real_free   = dlsym(RTLD_NEXT, "free");
}

static void wbuf(const char* s, int n) { ssize_t _r = write(2, s, n); (void)_r; }  /* direct write to stderr */

static int env_on(const char* name, int* cached) {
    if (*cached < 0) *cached = getenv(name) != NULL ? 1 : 0;
    return *cached;
}

static void emit(const char* op, void* p, size_t sz) {
    if (!env_on("MTRACE", &trace_on)) return;
    if (filter_sz && sz != (size_t)filter_sz) return;
    char buf[128];
    int n = snprintf(buf, sizeof(buf), "[mtrace] %s p=%p sz=%zu\n", op, p, sz);
    wbuf(buf, n);
    if (env_on("MTRACE_BACKTRACE", &bt_on)) {
        void* frames[12];
        int nf = backtrace(frames, 12);
        backtrace_symbols_fd(frames, nf, 2);  /* direct write to fd 2, bypassing printf */
    }
}

/* Constructor-time calloc can't use the dlsym result (may recurse); use a static buffer */
static char tmpbuf[8192]; static size_t tmpoff = 0;
void* calloc(size_t n, size_t sz) {
    if (!real_calloc) {
        if (in_hook) { size_t need=n*sz; if(tmpoff+need<=sizeof(tmpbuf)){void*p=tmpbuf+tmpoff;tmpoff+=need;return p;} return tmpbuf; }
        in_hook=1; init_real(); in_hook=0;
        if (!real_calloc) { /* still unavailable */ size_t need=n*sz; if(tmpoff+need<=sizeof(tmpbuf)){void*p=tmpbuf+tmpoff;tmpoff+=need;return p;} return tmpbuf; }
    }
    void* p = real_calloc(n, sz);
    if (!in_hook) { in_hook=1; emit("calloc", p, n*sz); in_hook=0; }
    return p;
}
void* malloc(size_t sz) {
    if (!real_malloc) { init_real(); }
    void* p = real_malloc ? real_malloc(sz) : NULL;
    if (!in_hook && p) { in_hook=1; emit("malloc", p, sz); in_hook=0; }
    return p;
}
void* realloc(void* old, size_t sz) {
    if (!real_realloc) { init_real(); }
    void* p = real_realloc ? real_realloc(old, sz) : NULL;
    if (!in_hook && p) { in_hook=1; emit("realloc", p, sz); in_hook=0; }
    return p;
}
void free(void* p) {
    if (!real_free) { init_real(); }
    if (p && (char*)p >= tmpbuf && (char*)p < tmpbuf+sizeof(tmpbuf)) return; /* static buffer; skip */
    if (real_free) real_free(p);
    if (!in_hook && p) { in_hook=1; emit("free", p, 0); in_hook=0; }
}

/* Initialize the filter at library load time */
__attribute__((constructor))
static void _init_box(void) {
    const char* f = getenv("MTRACE_FILTER");
    if (f) filter_sz = atoi(f);
    init_real();
}
