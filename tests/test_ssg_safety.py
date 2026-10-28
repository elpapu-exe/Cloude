#!/usr/bin/env python3
"""Run actual SSG policy/sysfs C bodies with deterministic lifetime boundaries."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    start = source.rfind('\n', 0, source.index(name + '(')) + 1
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


def run_c(program):
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / 'ssg-test.c'
        exe = Path(tmp) / 'ssg-test'
        src.write_text(program)
        subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-O1', '-g',
                        '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                        '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                        str(src), '-o', str(exe)], check=True, capture_output=True, text=True)
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)


POLICY_STUBS = r'''
#include <assert.h>
#include <stdlib.h>
#include <stdbool.h>
struct request_queue { int unused; };
struct ssg_blkg { int current_rqs; unsigned int max_available_rqs, shallow_depth; };
struct blkcg_gq { struct ssg_blkg *policy; };
static struct blkcg_gq group;
static bool locked;
#define IS_ERR_OR_NULL(x) (!(x))
#define BLKG_TO_SSG_BLKG(x) ((x)->policy)
static int blkcg_css(void) { return 0; }
static int css_to_blkcg(int css) { return css; }
static struct blkcg_gq *blkg_lookup(int css, struct request_queue *q) { return &group; }
static void rcu_read_lock(void) { assert(!locked); locked = true; }
static int atomic_read(int *p) { assert(locked); return *p; }
static void rcu_read_unlock(void) {
    assert(locked);
    locked = false;
    /* Simulate a grace period completing at the first permitted instant. */
    free(group.policy);
    group.policy = NULL;
}
static void install(unsigned int current, unsigned int max, unsigned int depth) {
    group.policy = malloc(sizeof(*group.policy));
    assert(group.policy);
    *group.policy = (struct ssg_blkg){ current, max, depth };
}
'''

SYSFS_STUBS = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <string.h>
#define READ 0
#define WRITE 1
struct ssg_data { int fifo_expire[2], max_write_starvation, front_merges; };
struct elevator_queue { struct ssg_data *elevator_data; };
static unsigned long msecs_to_jiffies(unsigned int value) { return value; }
/* Kernel kstrtoint contract: range/syntax errors must leave the output untouched. */
static int kstrtoint(const char *page, unsigned int base, int *output) {
    char *end;
    errno = 0;
    long value = strtol(page, &end, base);
    if (errno == ERANGE || value > INT_MAX || value < INT_MIN) return -ERANGE;
    if (end == page || (*end && strcmp(end, "\n"))) return -EINVAL;
    *output = value;
    return 0;
}
'''


class SsgSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cg = (ROOT / 'kernel-source/linux/block/ssg-cgroup.c').read_text()
        cls.io = (ROOT / 'kernel-source/linux/block/ssg-iosched.c').read_text()

    def test_policy_result_copied_before_grace_period(self):
        run_c(POLICY_STUBS + function(self.cg, 'ssg_blkcg_shallow_depth') + r'''
int main(void) {
    struct request_queue q;
    install(7, 7, 23);
    assert(ssg_blkcg_shallow_depth(&q) == 23);
    assert(!locked && !group.policy);
    install(8, 7, 19);
    assert(ssg_blkcg_shallow_depth(&q) == 19);
}
''')

    def test_policy_null_and_below_limit(self):
        run_c(POLICY_STUBS + function(self.cg, 'ssg_blkcg_shallow_depth') + r'''
int main(void) {
    struct request_queue q;
    assert(ssg_blkcg_shallow_depth(&q) == 0);
    install(6, 7, 23);
    assert(ssg_blkcg_shallow_depth(&q) == 0);
    assert(!locked && !group.policy);
}
''')

    def test_sysfs_rejects_bad_input_and_preserves_valid_clamps(self):
        stores = self.io[self.io.index('#define STORE_FUNCTION'):self.io.index('#undef STORE_FUNCTION')]
        run_c(SYSFS_STUBS + function(self.io, 'ssg_var_store') + stores + r'''
int main(void) {
    struct ssg_data ssg = { .front_merges = 1, .fifo_expire = {42, 43},
                            .max_write_starvation = 2 };
    struct elevator_queue e = { &ssg };
    assert(ssg_front_merges_store(&e, "bad", 3) == -EINVAL);
    assert(ssg.front_merges == 1);
    assert(ssg_front_merges_store(&e, "2147483648", 10) == -ERANGE);
    assert(ssg.front_merges == 1);
    assert(ssg_front_merges_store(&e, "-2147483649", 11) == -ERANGE);
    assert(ssg.front_merges == 1);
    assert(ssg_read_expire_store(&e, "9oops", 5) == -EINVAL);
    assert(ssg.fifo_expire[READ] == 42);
    assert(ssg_front_merges_store(&e, "-7", 2) == 2 && ssg.front_merges == 0);
    assert(ssg_front_merges_store(&e, "5\n", 2) == 2 && ssg.front_merges == 1);
    assert(ssg_read_expire_store(&e, "-1", 2) == 2 && ssg.fifo_expire[READ] == 0);
    assert(ssg_write_expire_store(&e, "2147483647", 10) == 10);
    assert(ssg.fifo_expire[WRITE] == INT_MAX);
    assert(ssg_max_write_starvation_store(&e, "-2147483648", 11) == 11);
    assert(ssg.max_write_starvation == INT_MIN);
}
''')


if __name__ == '__main__':
    unittest.main()
