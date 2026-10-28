#!/usr/bin/env python3
"""Test real governor start/store helpers under controlled thread interleavings.

Only tunable loads are instrumented to select a legal load/store schedule.
Mutex stubs use pthread locks and check attr_set -> min_rate ordering. These
host checks do not measure phone performance or prove all kernel concurrency.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
from source_path import SOURCE_ROOT

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r'static (?:inline )?[\w *\n]+\b' + name + r'\([^;]*?\)\n\{', source, re.S)
    if not match:
        raise AssertionError('missing real helper ' + name)
    end, depth = match.end(), 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <stddef.h>
#include <limits.h>
#include <errno.h>
typedef uint64_t u64; typedef int64_t s64;
#define NSEC_PER_USEC 1000L
#define CPUFREQ_NEED_UPDATE_LIMITS 1
#define min(a,b) ((a)<(b)?(a):(b))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
struct sugov_policy;
struct list_head { struct sugov_policy *one; };
struct mutex { pthread_mutex_t real; int kind; };
struct gov_attr_set { struct mutex update_lock; struct list_head policy_list; };
struct sugov_tunables {
    struct gov_attr_set attr_set;
    unsigned int rate_limit_us, up_rate_limit_us, down_rate_limit_us;
};
struct update_util_data { int placeholder; };
struct cpufreq_policy { void *governor_data; int cpus; bool fast_switch_enabled; };
struct sugov_policy {
    struct sugov_tunables *tunables;
    s64 freq_update_delay_ns, up_rate_delay_ns, down_rate_delay_ns, min_rate_limit_ns;
    u64 last_freq_update_time;
    unsigned int next_freq, cached_raw_freq;
    bool work_in_progress, limits_changed, need_freq_update, cached_raw_freq_valid;
};
struct sugov_cpu { struct update_util_data update_util; struct sugov_policy *sg_policy; unsigned int cpu; };
static struct sugov_cpu sugov_cpu[2];
static struct mutex min_rate_lock = {PTHREAD_MUTEX_INITIALIZER, 2};
static _Thread_local int attr_depth, min_depth;
static pthread_mutex_t event_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t event = PTHREAD_COND_INITIALIZER;
static bool writer_go, writer_done, writer_attempted;
static int inject_field = -1;
static void mutex_lock(struct mutex *m)
{
    if (m->kind == 1) assert(attr_depth == 0 && min_depth == 0);
    else assert(min_depth == 0);
    assert(!pthread_mutex_lock(&m->real));
    if (m->kind == 1) attr_depth++; else min_depth++;
}
static void mutex_unlock(struct mutex *m)
{
    if (m->kind == 1) { assert(attr_depth == 1 && min_depth == 0); attr_depth--; }
    else { assert(min_depth == 1); min_depth--; }
    assert(!pthread_mutex_unlock(&m->real));
}
#define list_for_each_entry(p,h,m) for ((p)=(h)->one; (p); (p)=NULL)
#define for_each_cpu(cpu,n) for ((cpu)=0;(cpu)<(unsigned)(n);(cpu)++)
#define per_cpu(array,cpu) ((array)[cpu])
static bool cpufreq_driver_test_flags(int flag) { (void)flag; return false; }
static bool cpufreq_driver_has_adjust_perf(void) { return false; }
static bool policy_is_shared(struct cpufreq_policy *p) { return p->cpus > 1; }
static void sugov_update_shared(struct update_util_data *d,u64 t,unsigned int f) { (void)d;(void)t;(void)f; }
static void sugov_update_single_perf(struct update_util_data *d,u64 t,unsigned int f) { (void)d;(void)t;(void)f; }
static void sugov_update_single_freq(struct update_util_data *d,u64 t,unsigned int f) { (void)d;(void)t;(void)f; }
static void cpufreq_add_update_util_hook(unsigned int c,struct update_util_data *d,
    void (*fn)(struct update_util_data *,u64,unsigned int)) { (void)c;(void)d;(void)fn; }
static int kstrtouint(const char *b,unsigned int base,unsigned int *out)
{
    char *end; errno = 0; unsigned long n = strtoul(b,&end,base);
    if (errno == ERANGE || n > UINT_MAX) return -ERANGE;
    if (end == b || *end) return -EINVAL;
    *out = n; return 0;
}
/* The selected load returns its snapshot after allowing the sysfs writer in. */
static unsigned int read_rate_limit(struct sugov_policy *p, int field)
{
    unsigned int snapshot = field == 0 ? p->tunables->rate_limit_us :
        field == 1 ? p->tunables->up_rate_limit_us : p->tunables->down_rate_limit_us;
    if (inject_field != field) return snapshot;
    pthread_mutex_lock(&event_lock);
    writer_go = true; pthread_cond_broadcast(&event);
    while (!writer_attempted) pthread_cond_wait(&event,&event_lock);
    if (!attr_depth) while (!writer_done) pthread_cond_wait(&event,&event_lock);
    pthread_mutex_unlock(&event_lock);
    return snapshot;
}
'''

SUFFIX = r'''
static void store_rate(struct sugov_tunables *t, int field, const char *value)
{
    ssize_t result;
    /* This is the lock taken by the real governor_store() sysfs dispatcher. */
    mutex_lock(&t->attr_set.update_lock);
#ifdef HORIZON
    result = field == 1 ? up_rate_limit_us_store(&t->attr_set,value,strlen(value)) :
        down_rate_limit_us_store(&t->attr_set,value,strlen(value));
#else
    (void)field;
    result = rate_limit_us_store(&t->attr_set,value,strlen(value));
#endif
    assert(result == (ssize_t)strlen(value));
    mutex_unlock(&t->attr_set.update_lock);
}
static void *writer_once(void *arg)
{
    pthread_mutex_lock(&event_lock);
    while (!writer_go) pthread_cond_wait(&event,&event_lock);
    writer_attempted = true; pthread_cond_broadcast(&event);
    pthread_mutex_unlock(&event_lock);
    store_rate(arg,inject_field,"2000");
    pthread_mutex_lock(&event_lock); writer_done = true; pthread_cond_broadcast(&event);
    pthread_mutex_unlock(&event_lock);
    return NULL;
}
static void *writer_repeat(void *arg)
{
    char value[32];
    for (int i = 1; i <= 4000; i++) {
        snprintf(value,sizeof(value),"%u",(unsigned)(i % 100 + 10));
        store_rate(arg,1,value);
#ifdef HORIZON
        snprintf(value,sizeof(value),"%u",(unsigned)(i % 30 + 50));
        store_rate(arg,2,value);
#endif
    }
    return NULL;
}
static void verify(struct sugov_tunables *t, struct sugov_policy *p)
{
#ifdef HORIZON
    assert(p->up_rate_delay_ns == (s64)t->up_rate_limit_us * NSEC_PER_USEC);
    assert(p->down_rate_delay_ns == (s64)t->down_rate_limit_us * NSEC_PER_USEC);
    assert(p->min_rate_limit_ns == min(p->up_rate_delay_ns,p->down_rate_delay_ns));
#else
    assert(p->freq_update_delay_ns == (s64)t->rate_limit_us * NSEC_PER_USEC);
#endif
}
int main(int argc, char **argv)
{
    assert(argc == 2); int scenario = atoi(argv[1]);
    struct sugov_tunables t = {.rate_limit_us=1000,.up_rate_limit_us=1000,.down_rate_limit_us=3000};
    assert(!pthread_mutex_init(&t.attr_set.update_lock.real,NULL)); t.attr_set.update_lock.kind = 1;
    struct sugov_policy p = {.tunables=&t}; t.attr_set.policy_list.one = &p;
    struct cpufreq_policy policy = {.governor_data=&p,.cpus=2}; pthread_t thread;
    if (scenario < 3) {
        inject_field = scenario;
        assert(!pthread_create(&thread,NULL,writer_once,&t));
        assert(!sugov_start(&policy)); assert(!pthread_join(thread,NULL));
        verify(&t,&p);
    } else if (scenario == 3) {
        const unsigned int rates[] = {0,1,500,UINT_MAX};
        for (unsigned int i = 0; i < sizeof(rates)/sizeof(rates[0]); i++) {
            t.rate_limit_us = t.up_rate_limit_us = rates[i];
            t.down_rate_limit_us = rates[sizeof(rates)/sizeof(rates[0])-i-1];
            assert(!sugov_start(&policy)); verify(&t,&p);
        }
    } else if (scenario == 4) {
        assert(!pthread_create(&thread,NULL,writer_repeat,&t));
        for (int i = 0; i < 4000; i++) assert(!sugov_start(&policy));
        assert(!pthread_join(thread,NULL));
#if FIXED
        verify(&t,&p);
#endif
    } else abort();
    assert(attr_depth == 0 && min_depth == 0);
    assert(!pthread_mutex_destroy(&t.attr_set.update_lock.real));
    return 0;
}
'''


class StartSerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='cpufreq-start-')
        cls.binaries = {}
        for mode in ('schedutil', 'schedhorizon'):
            for fixed in (False, True):
                path = SOURCE_ROOT / ('kernel/sched/cpufreq_' + mode + '.c') if fixed else (
                    ROOT / ('tests/fixtures/cpufreq-start-rc3-' + mode + '.c'))
                source = path.read_text()
                names = ('to_sugov_tunables', 'rate_limit_us_store') if mode == 'schedutil' else (
                    'to_sugov_tunables', 'update_min_rate_limit_ns',
                    'up_rate_limit_us_store', 'down_rate_limit_us_store')
                helpers = '\n\n'.join(function(source, name) for name in names)
                start = function(source, 'sugov_start')
                # Substitute only tunable loads, preserving the production stores/locks.
                for field, number in (('rate_limit_us', 0), ('up_rate_limit_us', 1), ('down_rate_limit_us', 2)):
                    start = start.replace('sg_policy->tunables->' + field,
                                          f'read_rate_limit(sg_policy, {number})')
                label = mode + ('-fixed' if fixed else '-before')
                binary = Path(cls.directory.name) / label
                defines = f'#define FIXED {int(fixed)}\n'
                if mode == 'schedhorizon':
                    defines += '#define HORIZON\n'
                binary.with_suffix('.c').write_text(defines + PREFIX + helpers + '\n' + start + SUFFIX)
                build = subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-O1', '-g',
                    '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-no-pie', '-pthread', str(binary.with_suffix('.c')),
                    '-o', str(binary)], capture_output=True, text=True)
                if build.returncode:
                    raise AssertionError(build.stderr)
                cls.binaries[(mode, fixed)] = binary

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_scenario(self, mode, scenario, *, regression=False):
        for fixed in (True, False):
            result = subprocess.run([str(self.binaries[(mode, fixed)]), str(scenario)],
                capture_output=True, text=True, timeout=15,
                env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                         UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))
            if regression and not fixed:
                self.assertNotEqual(result.returncode, 0, 'frozen pre-fix control unexpectedly passes')
                self.assertIn('Assertion', result.stderr)
            else:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_schedutil_interleaved_start_store(self):
        self.run_scenario('schedutil', 0, regression=True)

    def test_horizon_up_and_down_interleavings(self):
        self.run_scenario('schedhorizon', 1, regression=True)
        self.run_scenario('schedhorizon', 2, regression=True)

    def test_normal_rate_values_unchanged(self):
        for mode in ('schedutil', 'schedhorizon'):
            self.run_scenario(mode, 3)

    def test_repeated_concurrent_start_store_has_no_deadlock(self):
        for mode in ('schedutil', 'schedhorizon'):
            self.run_scenario(mode, 4)


if __name__ == '__main__':
    unittest.main()
