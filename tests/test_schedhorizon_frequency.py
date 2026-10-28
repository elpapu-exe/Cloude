#!/usr/bin/env python3
"""Compile real Horizon frequency helpers with deterministic driver/hook stubs.

These are unit checks of governor state transitions, not a performance or
concurrency proof. Frozen pre-fix helpers must reject ten regression scenarios.
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
FIXTURE = ROOT / 'tests/fixtures/schedhorizon-rc2-frequency.c'
FUNCTIONS = ('sugov_should_update_freq', 'sugov_up_down_rate_limit',
             'sugov_update_next_freq', 'get_next_freq')


def extract_function(source, name):
    match = re.search(r'static (?:inline )?[\w ]+\b' + name + r'\([^;]*?\)\n\{', source, re.S)
    if not match:
        raise AssertionError(f'missing real helper {name}')
    cursor, depth = match.end(), 1
    while depth:
        depth += (source[cursor] == '{') - (source[cursor] == '}')
        cursor += 1
    return source[match.start():cursor]


PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
typedef uint64_t u64;
typedef int64_t s64;
#define unlikely(x) (x)
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x, value) ((x) = (value))
#define smp_mb() do { full_barriers++; } while (0)
#define CPUFREQ_NEED_UPDATE_LIMITS 1
#define CPUFREQ_RELATION_H 1
#define clamp(v, lo, hi) ((v) < (lo) ? (lo) : ((v) > (hi) ? (hi) : (v)))
#define mult_frac(x, n, d) ((x) * (n) / (d))
struct cpufreq_frequency_table { unsigned int frequency; };
struct cpufreq_policy {
    struct { unsigned int max_freq; } cpuinfo;
    unsigned int min, max;
    struct cpufreq_frequency_table *freq_table;
};
struct sugov_policy {
    struct cpufreq_policy *policy;
    u64 last_freq_update_time;
    s64 min_rate_limit_ns, up_rate_delay_ns, down_rate_delay_ns;
    unsigned int next_freq, cached_raw_freq;
    bool cached_raw_freq_valid, limits_changed, need_freq_update;
};
static bool allow_update = true, vendor_accept = true, driver_need_limits;
static int resolve_calls, hook_calls, full_barriers;
static bool cpufreq_this_cpu_can_update(struct cpufreq_policy *p) { (void)p; return allow_update; }
static bool cpufreq_driver_test_flags(int flag) { assert(flag == CPUFREQ_NEED_UPDATE_LIMITS); return driver_need_limits; }
static void trace_android_rvh_set_sugov_update(struct sugov_policy *p, unsigned int f, bool *accept)
{ (void)p; (void)f; hook_calls++; *accept = vendor_accept; }
static unsigned long map_util_perf(unsigned long u) { return u; }
static unsigned int map_util_freq(unsigned long u, unsigned int f, unsigned long m) { return u * f / m; }
static void trace_android_vh_map_util_freq(unsigned long u, unsigned int f, unsigned long m, unsigned long *next)
{ (void)u; (void)f; (void)m; (void)next; }
static void trace_android_vh_map_util_freq_new(unsigned long u, unsigned int f, unsigned long m, unsigned long *next,
    struct cpufreq_policy *p, bool *force)
{ (void)u; (void)f; (void)m; (void)next; (void)p; (void)force; }
/* Tunable-table limiting has its own test suite; isolate frequency-cache state here. */
static void do_freq_limit(struct sugov_policy *p, unsigned int *f, u64 t) { (void)p; (void)f; (void)t; }
static unsigned int cpufreq_driver_resolve_freq(struct cpufreq_policy *p, unsigned int f)
{ resolve_calls++; return clamp(f, p->min, p->max); }
static unsigned int cpufreq_frequency_table_target(struct cpufreq_policy *p, unsigned int f, int relation)
{ (void)p; (void)f; assert(relation == CPUFREQ_RELATION_H); return 0; }
'''

HARNESS = r'''
static unsigned int demand(struct sugov_policy *p, unsigned int raw, u64 time)
{ return get_next_freq(p, raw, 1000, time); }
int main(int argc, char **argv)
{
    assert(argc == 2);
    struct cpufreq_frequency_table table[] = {{0}};
    struct cpufreq_policy policy = {.cpuinfo = {1000}, .min = 100, .max = 1000, .freq_table = table};
    struct sugov_policy p = {.policy = &policy, .last_freq_update_time = 1000,
        .min_rate_limit_ns = 20, .up_rate_delay_ns = 100, .down_rate_delay_ns = 200, .next_freq = 400};
    unsigned int f;
    switch (atoi(argv[1])) {
    case 0: /* Rejected upward demand must be retried after the delay. */
        f = demand(&p, 700, 1010);
        assert(!sugov_update_next_freq(&p, 1010, f));
        f = demand(&p, 700, 1200);
        assert(sugov_update_next_freq(&p, 1200, f));
        assert(p.next_freq == 700 && resolve_calls == 2);
        break;
    case 1: /* Same transition, downward direction. */
        f = demand(&p, 200, 1050);
        assert(!sugov_update_next_freq(&p, 1050, f));
        f = demand(&p, 200, 1250);
        assert(sugov_update_next_freq(&p, 1250, f));
        assert(p.next_freq == 200 && resolve_calls == 2);
        break;
    case 2: /* Provider veto must not poison the raw-frequency cache. */
        vendor_accept = false;
        f = demand(&p, 700, 1300);
        assert(!sugov_update_next_freq(&p, 1300, f));
        vendor_accept = true;
        f = demand(&p, 700, 1301);
        assert(sugov_update_next_freq(&p, 1301, f));
        assert(p.next_freq == 700 && resolve_calls == 2);
        break;
    case 3: /* A veto preserves a forced update and allows it through a delay. */
        p.need_freq_update = true;
        vendor_accept = false;
        f = demand(&p, 700, 1001);
        assert(!sugov_update_next_freq(&p, 1001, f));
        assert(p.need_freq_update && !p.cached_raw_freq_valid);
        vendor_accept = true;
        assert(sugov_should_update_freq(&p, 1002));
        f = demand(&p, 700, 1002);
        assert(sugov_update_next_freq(&p, 1002, f));
        assert(!p.need_freq_update && p.next_freq == 700);
        break;
    case 4: /* A forced upward change bypasses the upward delay. */
        p.need_freq_update = true;
        assert(sugov_update_next_freq(&p, 1001, 800));
        assert(p.next_freq == 800 && !p.need_freq_update);
        break;
    case 5: /* A forced downward change bypasses the downward delay. */
        p.need_freq_update = true;
        assert(sugov_update_next_freq(&p, 1001, 200));
        assert(p.next_freq == 200 && !p.need_freq_update);
        break;
    case 6: /* Equal resolved value needs no driver callback without its flag. */
        p.need_freq_update = true;
        assert(!sugov_update_next_freq(&p, 1300, p.next_freq));
        assert(!p.need_freq_update && hook_calls == 0 && p.last_freq_update_time == 1000);
        break;
    case 7: /* The driver's explicit request requires an equal-value update. */
        p.need_freq_update = true;
        driver_need_limits = true;
        assert(sugov_update_next_freq(&p, 1300, p.next_freq));
        assert(!p.need_freq_update && hook_calls == 1 && p.last_freq_update_time == 1300);
        break;
    case 8: /* Zero is a valid raw request, not a cache sentinel. */
        f = demand(&p, 0, 1300);
        assert(f == policy.min && resolve_calls == 1);
        break;
    case 9: /* A force remaining after a veto bypasses the minimum delay. */
        p.need_freq_update = true;
        assert(sugov_should_update_freq(&p, 1001));
        break;
    case 10: /* Successful requests retain the normal raw-frequency cache. */
        f = demand(&p, 700, 1300);
        assert(sugov_update_next_freq(&p, 1300, f));
        assert(demand(&p, 700, 1400) == 700 && resolve_calls == 1);
        assert(!sugov_update_next_freq(&p, 1400, 700));
        assert(p.last_freq_update_time == 1300 && hook_calls == 1);
        break;
    case 11: /* Remote restrictions and ordinary minimum delay remain honored. */
        allow_update = false;
        p.limits_changed = true;
        assert(!sugov_should_update_freq(&p, 1300) && p.limits_changed);
        allow_update = true;
        p.limits_changed = false;
        assert(!sugov_should_update_freq(&p, 1001));
        assert(sugov_should_update_freq(&p, 1100));
        break;
    default: abort();
    }
    return 0;
}
'''


class FrequencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        cls.binaries = []
        for label, path in [('fixed', SOURCE), ('before', FIXTURE)]:
            helpers = '\n\n'.join(extract_function(path.read_text(), name) for name in FUNCTIONS)
            cfile, binary = cls.directory / (label + '.c'), cls.directory / label
            cfile.write_text(PRELUDE + helpers + HARNESS)
            build = subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-O1', '-g',
                '-Wall', '-Wextra', '-Werror', '-Wno-unused-variable', '-Wno-unused-function', '-no-pie',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(cfile), '-o', str(binary)],
                capture_output=True, text=True)
            if build.returncode:
                raise AssertionError(build.stderr)
            cls.binaries.append(binary)
        # A source contract for memory ordering, distinct from host-stub behavior.
        source = SOURCE.read_text()
        reader = extract_function(source, 'sugov_should_update_freq')
        writer = extract_function(source, 'sugov_limits')
        if not ('READ_ONCE(sg_policy->limits_changed)' in reader and
                'WRITE_ONCE(sg_policy->limits_changed, false)' in reader and
                'smp_mb()' in reader and 'smp_wmb()' in writer and
                'WRITE_ONCE(sg_policy->limits_changed, true)' in writer):
            raise AssertionError('limits publication/consumption barriers missing')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_scenario(self, scenario):
        fixed = subprocess.run([str(self.binaries[0]), str(scenario)], env=self.env,
                               capture_output=True, text=True)
        self.assertEqual(fixed.returncode, 0, fixed.stderr)
        old = subprocess.run([str(self.binaries[1]), str(scenario)], env=self.env,
                             capture_output=True, text=True)
        if scenario < 10:
            self.assertNotEqual(old.returncode, 0, 'negative control unexpectedly passes')
            self.assertIn('Assertion', old.stderr, old.stderr)
        else:
            self.assertEqual(old.returncode, 0, old.stderr)


def add_scenario(scenario):
    def check(self):
        self.run_scenario(scenario)
    return check


for index, name in enumerate(('rejected_up_retry', 'rejected_down_retry', 'veto_retry',
    'forced_veto_retry', 'forced_up', 'forced_down', 'equal_no_driver_flag',
    'equal_driver_flag', 'raw_zero', 'pending_force_min_delay', 'normal_cache', 'normal_gating')):
    setattr(FrequencyTests, 'test_' + name, add_scenario(index))

if __name__ == '__main__':
    unittest.main()
