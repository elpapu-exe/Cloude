#!/usr/bin/env python3
"""Exercise production table helpers with ASan/UBSan and pthread-backed locks.

Host locks model exclusion and expose pointer lifetime errors; these checks are
not a kernel scheduler stress test or a formal proof of memory ordering.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
from source_path import SOURCE_ROOT

ROOT = Path(__file__).resolve().parents[1]
SOURCE = SOURCE_ROOT / 'kernel/sched/cpufreq_schedhorizon.c'


def function(source, name):
    match = re.search(r'static (?:inline )?[\w *]+\b' + name + r'\([^;]*?\)\n\{', source, re.S)
    if not match:
        raise AssertionError('missing production helper ' + name)
    cursor, depth = match.end(), 1
    while depth:
        depth += (source[cursor] == '{') - (source[cursor] == '}')
        cursor += 1
    return source[match.start():cursor]


PREFIX = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdatomic.h>
#include <string.h>
#include <sys/types.h>
typedef uint64_t u64;
#define PAGE_SIZE 4096
#define NSEC_PER_MSEC 1000000ULL
#define U64_MAX UINT64_MAX
#define GFP_KERNEL 0
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((intptr_t)(x))
#define IS_ERR(x) ((uintptr_t)(x) >= (uintptr_t)-4095)
#define ERR_CAST(x) ((void *)(x))
#define min(a,b) ((a) < (b) ? (a) : (b))
#define min_t(type,a,b) min((type)(a), (type)(b))
#define clamp(x,lo,hi) ((x) < (lo) ? (lo) : ((x) > (hi) ? (hi) : (x)))
#define WARN_ON_ONCE(x) (x)
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
typedef pthread_mutex_t raw_spinlock_t;
static _Thread_local int lock_depth, fail_allocation_at, allocation_calls;
static _Thread_local void (*allocation_hook)(void);
static atomic_long live_allocations;
#define raw_spin_lock_irqsave(lock, flags) do { (flags) = 0; assert(lock_depth == 0); assert(!pthread_mutex_lock(lock)); lock_depth++; } while (0)
#define raw_spin_unlock_irqrestore(lock, flags) do { (void)(flags); assert(lock_depth == 1); lock_depth--; assert(!pthread_mutex_unlock(lock)); } while (0)
struct kobject { int placeholder; };
struct gov_attr_set { struct kobject kobj; };
struct sugov_tunables {
    raw_spinlock_t table_lock;
    struct gov_attr_set attr_set;
    unsigned int up_rate_limit_us, down_rate_limit_us;
    unsigned int *efficient_freq;
    int nefficient_freq;
    u64 *up_delay;
    int nup_delay, current_step;
};
struct sugov_policy { struct sugov_tunables *tunables; u64 first_hp_request_time; };
static unsigned int default_efficient_freq[] = {0};
static u64 default_up_delay[] = {0};
static void *allocate(size_t size)
{
    assert(lock_depth == 0);
    if (allocation_hook) { void (*hook)(void) = allocation_hook; allocation_hook = NULL; hook(); }
    allocation_calls++;
    if (fail_allocation_at && allocation_calls == fail_allocation_at) return NULL;
    void *p = malloc(size);
    if (p) atomic_fetch_add(&live_allocations, 1);
    return p;
}
static void *kmalloc_array(size_t n, size_t size, int flags)
{ (void)flags; if (size && n > SIZE_MAX / size) return NULL; return allocate(n * size); }
static char *kmemdup_nul(const char *s, size_t n, int flags)
{ (void)flags; char *p = allocate(n + 1); if (p) { memcpy(p, s, n); p[n] = 0; } return p; }
static void kfree(void *p)
{ assert(lock_depth == 0); if (p) { atomic_fetch_sub(&live_allocations, 1); free(p); } }
static int kstrtou64(const char *s, unsigned int base, u64 *out)
{
    char *end; unsigned long long result;
    errno = 0; result = strtoull(s, &end, base);
    if (errno == ERANGE) return -ERANGE;
    if (end == s || (*end && !(*end == '\n' && !end[1]))) return -EINVAL;
    *out = result; return 0;
}
static int scnprintf(char *buf, size_t size, const char *format, ...)
{
    va_list args; va_start(args, format);
    int n = vsnprintf(buf, size, format, args); va_end(args);
    assert(n >= 0);
    return size ? min(n, (int)size - 1) : 0;
}
'''

SUFFIX = r'''
static struct sugov_tunables *active;
static void init(struct sugov_tunables *t)
{
    memset(t, 0, sizeof(*t));
    assert(!pthread_mutex_init(&t->table_lock, NULL));
    t->efficient_freq = default_efficient_freq; t->nefficient_freq = 1;
    t->up_delay = default_up_delay; t->nup_delay = 1;
}
static void clean(struct sugov_tunables *t)
{
    if (t->efficient_freq != default_efficient_freq) kfree(t->efficient_freq);
    if (t->up_delay != default_up_delay) kfree(t->up_delay);
    assert(!pthread_mutex_destroy(&t->table_lock));
}
static void resize_grow(void)
{
    assert(efficient_freq_store(&active->attr_set, "100 200 300 400", 15) == 15);
}
static void resize_shrink(void)
{
    assert(efficient_freq_store(&active->attr_set, "80", 2) == 2);
}
static void *writer(void *arg)
{
    struct sugov_tunables *t = arg;
    for (int i = 0; i < 5000; i++) {
        const char *freq = i & 1 ? "100 300 700 900" : "400";
        const char *delay = i & 1 ? "0" : "1 2 3 4 5 6 7";
        assert(efficient_freq_store(&t->attr_set, freq, strlen(freq)) == (ssize_t)strlen(freq));
        assert(up_delay_store(&t->attr_set, delay, strlen(delay)) == (ssize_t)strlen(delay));
    }
    return NULL;
}
static void *reader(void *arg)
{
    struct sugov_tunables *t = arg; char text[PAGE_SIZE];
    for (int i = 0; i < 5000; i++) {
        ssize_t n = efficient_freq_show(&t->attr_set, text);
        assert(n > 0 && n < PAGE_SIZE && text[n - 1] == '\n');
        n = up_delay_show(&t->attr_set, text);
        assert(n > 0 && n < PAGE_SIZE && text[n - 1] == '\n');
    }
    return NULL;
}
static void *limiter(void *arg)
{
    struct sugov_policy policy = {.tunables = arg};
    for (int i = 1; i < 10000; i++) {
        unsigned int freq = i % 1000;
        do_freq_limit(&policy, &freq, i * NSEC_PER_MSEC);
        assert(freq <= 1000);
    }
    return NULL;
}
int main(int argc, char **argv)
{
    assert(argc == 2);
    struct sugov_tunables t; init(&t); active = &t;
    struct sugov_policy policy = {.tunables = &t};
    char buffer[PAGE_SIZE + 2], text[PAGE_SIZE];
    unsigned int *freq, value; u64 *delay; int n = -1;
    switch (atoi(argv[1])) {
    case 0: /* Strict parsing, bounds, and complete-token validation. */
        freq = resolve_data_freq(" \t0 200 4294967295\n", &n, 19);
        assert(!IS_ERR(freq) && n == 3 && freq[2] == UINT_MAX); kfree(freq);
        const char *invalid[] = {"", " ", "+3", "-1", "1x", "1,2", "200 100", "4294967296", "18446744073709551616"};
        for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); i++)
            assert(IS_ERR(resolve_data_freq(invalid[i], &n, strlen(invalid[i]))));
        assert(IS_ERR(resolve_data_freq("1\0x", &n, 3)));
        memset(buffer, '1', PAGE_SIZE + 1);
        assert(IS_ERR(resolve_data_freq(buffer, &n, PAGE_SIZE + 1)));
        for (int i = 0; i < HORIZON_TABLE_MAX + 1; i++) { buffer[2*i] = '1'; buffer[2*i+1] = ' '; }
        assert(PTR_ERR(resolve_data_freq(buffer, &n, 2*(HORIZON_TABLE_MAX + 1))) == -ERANGE);
        break;
    case 1: /* Overflow-free ms conversion, output formatting and time addition. */
        delay = resolve_data_delay("18446744073709", &n, 14);
        assert(!IS_ERR(delay) && n == 1 && delay[0] == 18446744073709000000ULL); kfree(delay);
        assert(PTR_ERR(resolve_data_delay("18446744073710", &n, 14)) == -ERANGE);
        assert(up_delay_store(&t.attr_set, "18446744073709 0", 16) == 16);
        assert(up_delay_show(&t.attr_set, text) == 17);
        assert(!strcmp(text, "18446744073709 0\n"));
        assert(efficient_freq_store(&t.attr_set, "100 200", 7) == 7);
        policy.first_hp_request_time = 1000000;
        value = 300; do_freq_limit(&policy, &value, 1000001);
        assert(value == 100 && t.current_step == 0);
        break;
    case 2: /* OOM and parse failures preserve the old published table. */
        assert(efficient_freq_store(&t.attr_set, "100 200", 7) == 7);
        unsigned int *original = t.efficient_freq;
        for (int i = 1; i <= 3; i++) {
            allocation_calls = 0; fail_allocation_at = i;
            assert(efficient_freq_store(&t.attr_set, "300 400", 7) == -ENOMEM);
            assert(t.efficient_freq == original && t.nefficient_freq == 2 && original[0] == 100);
        }
        fail_allocation_at = 0;
        assert(efficient_freq_store(&t.attr_set, "-4", 2) == -EINVAL && t.efficient_freq == original);
        allocation_calls = 0; fail_allocation_at = 1;
        assert(efficient_freq_show(&t.attr_set, text) == -ENOMEM);
        fail_allocation_at = 0;
        /* Exercise the production kobject release on its actual owned arrays. */
        struct sugov_tunables *owned = allocate(sizeof(*owned)); init(owned);
        assert(efficient_freq_store(&owned->attr_set, "20 40", 5) == 5);
        assert(up_delay_store(&owned->attr_set, "1 2 3", 5) == 5);
        assert(!pthread_mutex_destroy(&owned->table_lock));
        sugov_tunables_free(&owned->attr_set.kobj);
        break;
    case 3: /* Bound the index by both lengths and handle read-time resizing. */
        assert(efficient_freq_store(&t.attr_set, "100 200 300", 11) == 11);
        assert(up_delay_store(&t.attr_set, "0", 1) == 1);
        t.current_step = 500; value = 800; do_freq_limit(&policy, &value, 1);
        assert(t.current_step == 0 && value == 100);
        assert(efficient_freq_store(&t.attr_set, "300", 3) == 3);
        assert(up_delay_store(&t.attr_set, "0 1 2 3", 7) == 7);
        t.current_step = -10; policy.first_hp_request_time = 0; value = 800;
        do_freq_limit(&policy, &value, 2); assert(t.current_step == 0 && value == 300);
        allocation_hook = resize_grow;
        assert(efficient_freq_show(&t.attr_set, text) == 4 && !strcmp(text, "100\n"));
        allocation_hook = resize_shrink;
        assert(efficient_freq_show(&t.attr_set, text) == 3 && !strcmp(text, "80\n"));
        assert(match_nearest_efficient_step(UINT_MAX, 1, t.efficient_freq) == 0);
        break;
    case 4: /* Simultaneous readers/writer/limiter must not retain freed arrays. */
        pthread_t a, b, c;
        assert(!pthread_create(&a, NULL, writer, &t));
        assert(!pthread_create(&b, NULL, reader, &t));
        assert(!pthread_create(&c, NULL, limiter, &t));
        assert(!pthread_join(a, NULL)); assert(!pthread_join(b, NULL)); assert(!pthread_join(c, NULL));
        break;
    default: abort();
    }
    clean(&t);
    assert(atomic_load(&live_allocations) == 0);
    return 0;
}
'''


class TunablesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        source = SOURCE.read_text()
        names = ('match_nearest_efficient_step', 'do_freq_limit', 'resolve_table',
                 'resolve_data_freq', 'resolve_data_delay', 'to_sugov_tunables',
                 'horizon_table_show', 'efficient_freq_show', 'up_delay_show',
                 'efficient_freq_store', 'up_delay_store', 'sugov_tunables_free')
        helpers = '\n\n'.join(function(source, name) for name in names)
        macro = re.search(r'^#define HORIZON_TABLE_MAX[^\n]+', source, re.M).group()
        path = Path(cls.directory.name)
        (path / 'test.c').write_text(PREFIX + macro + '\n' + helpers + SUFFIX)
        cls.binary = path / 'test'
        build = subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-O1', '-g',
            '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie', '-pthread',
            '-Wall', '-Wextra', '-Werror', str(path / 'test.c'), '-o', str(cls.binary)],
            capture_output=True, text=True)
        if build.returncode:
            raise AssertionError(build.stderr)
        # This start-time expression must stay syntactically valid and widen before multiply.
        start = function(source, 'sugov_start')
        for name in ('up', 'down'):
            expression = f'(u64)sg_policy->tunables->{name}_rate_limit_us * NSEC_PER_USEC'
            if expression not in start:
                raise AssertionError('missing widened start expression: ' + expression)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def scenario(self, index):
        result = subprocess.run([str(self.binary), str(index)], capture_output=True, text=True,
            env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_strict_parser(self): self.scenario(0)
    def test_delay_overflow_and_output(self): self.scenario(1)
    def test_failed_replacement_is_atomic(self): self.scenario(2)
    def test_both_bounds_and_read_resize(self): self.scenario(3)
    def test_concurrent_read_write_limit(self): self.scenario(4)


if __name__ == '__main__':
    unittest.main()
