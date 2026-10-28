#!/usr/bin/env python3
"""Compile Binder's real size/guard prefix and exercise quota boundaries.

The red-black tree/page allocation suffix is replaced by a success sentinel:
these are host regressions for validation and quota admission, not Binder IPC
or phone performance tests. The opaque metadata fixture is deliberately not
claimed to reproduce the ARM64 binder_buffer layout.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from source_path import SOURCE_ROOT

SOURCE = SOURCE_ROOT / 'drivers/android/binder_alloc.c'
GUARD = 'if (is_async && alloc->free_async_space < size) {'
LEGACY_GUARD = ('if (is_async &&\n'
                '\t    alloc->free_async_space < size + sizeof(struct binder_buffer)) {')

PREFIX = r'''
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define __user
#define ALIGN(value, alignment) (((value) + (alignment) - 1) & ~((alignment) - 1))
#define max(a, b) ((a) > (b) ? (a) : (b))
#define ERR_PTR(error) ((void *)(intptr_t)(error))
#define PTR_ERR(pointer) ((intptr_t)(pointer))
#define IS_ERR(pointer) ((uintptr_t)(pointer) >= (uintptr_t)-4095)
#define binder_alloc_debug(...) do {} while (0)
struct rb_node { int unused; };
struct binder_buffer { unsigned char opaque_fixture[104]; };
struct binder_alloc {
    struct { struct rb_node *rb_node; } free_buffers;
    size_t free_async_space;
    int pid;
    bool mapped;
};
static struct binder_buffer success;
static unsigned int hook_calls;
static size_t hook_size, *hook_quota, replacement_quota;
static int hook_async;
static bool change_quota;
static bool binder_alloc_get_vma(struct binder_alloc *alloc) { return alloc->mapped; }
static void trace_android_vh_binder_alloc_new_buf_locked(size_t size, size_t *quota,
                                                       int is_async)
{
    hook_calls++;
    hook_size = size;
    hook_quota = quota;
    hook_async = is_async;
    if (change_quota) *quota = replacement_quota;
}
'''

SUFFIX = r'''
#define CHECK(test, message) do { if (!(test)) { fprintf(stderr, "%s\n", message); return 1; } } while (0)
static void reset_hook(void)
{
    hook_calls = 0; hook_size = 0; hook_quota = NULL;
    hook_async = -1; change_quota = false; replacement_quota = 0;
}
static struct binder_buffer *probe(struct binder_alloc *alloc, size_t data,
                                   size_t offsets, size_t extra, int is_async)
{
    return binder_alloc_new_buf_locked(alloc, data, offsets, extra, is_async, 73);
}
int main(int argc, char **argv)
{
    CHECK(argc == 2, "missing scenario");
    const size_t word = sizeof(void *), metadata = sizeof(struct binder_buffer);
    struct binder_alloc alloc = { .mapped = true, .pid = 42 };
    struct binder_buffer *result;
    int scenario = atoi(argv[1]);
    reset_hook();
    if (scenario == 0) {
        /* All aligned payloads and the entire formerly inaccessible band. */
        for (size_t words = 1; words <= 64; words++) {
            size_t size = words * word;
            for (size_t quota = size; quota < size + metadata; quota++) {
                alloc.free_async_space = quota; reset_hook();
                result = probe(&alloc, size, 0, 0, 1);
                CHECK(result == &success, "guard rejected usable quota");
                CHECK(hook_calls == 1 && hook_size == size, "hook size/call changed");
                CHECK(hook_quota == &alloc.free_async_space && hook_async == 1,
                      "hook signature/arguments changed");
                CHECK(alloc.free_async_space == quota, "admission changed quota");
            }
        }
    } else if (scenario == 1) {
        for (size_t size = word; size <= 64 * word; size += word) {
            alloc.free_async_space = size - 1;
            result = probe(&alloc, size, 0, 0, 1);
            CHECK(IS_ERR(result) && PTR_ERR(result) == -ENOSPC,
                  "insufficient async quota accepted");
            CHECK(alloc.free_async_space == size - 1, "failed admission changed quota");
            alloc.free_async_space = 0;
            CHECK(probe(&alloc, size, 0, 0, 0) == &success,
                  "synchronous admission incorrectly uses async quota");
            alloc.free_async_space = size + metadata;
            CHECK(probe(&alloc, size, 0, 0, 1) == &success,
                  "ordinary async quota rejected");
        }
    } else if (scenario == 2) {
        alloc.free_async_space = word;
        result = probe(&alloc, 0, 0, 0, 1);
        CHECK(result == &success && hook_size == word,
              "empty parcel padding/quota incorrect");
        alloc.free_async_space = word - 1;
        result = probe(&alloc, 0, 0, 0, 1);
        CHECK(IS_ERR(result) && PTR_ERR(result) == -ENOSPC,
              "empty parcel bypassed padded quota");
        alloc.free_async_space = 3 * word;
        CHECK(probe(&alloc, 1, 1, 1, 1) == &success && hook_size == 3 * word,
              "individual alignment or exact quota incorrect");
        alloc.free_async_space = 3 * word - 1;
        result = probe(&alloc, 1, 1, 1, 1);
        CHECK(IS_ERR(result) && PTR_ERR(result) == -ENOSPC,
              "alignment shortage accepted");
    } else if (scenario == 3) {
        const size_t bad[][3] = {
            {SIZE_MAX, 0, 0}, {0, SIZE_MAX, 0}, {0, 0, SIZE_MAX},
            {SIZE_MAX - word + 1, word, 0},
            {SIZE_MAX - word + 1, 0, word},
        };
        alloc.free_async_space = SIZE_MAX;
        for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
            reset_hook();
            result = probe(&alloc, bad[i][0], bad[i][1], bad[i][2], 1);
            CHECK(IS_ERR(result) && PTR_ERR(result) == -EINVAL,
                  "overflow validation changed");
            CHECK(!hook_calls && alloc.free_async_space == SIZE_MAX,
                  "invalid request reached hook or modified quota");
        }
    } else if (scenario == 4) {
        alloc.free_async_space = 0;
        change_quota = true; replacement_quota = word;
        CHECK(probe(&alloc, 1, 0, 0, 1) == &success,
              "guard ignored hook-provided quota");
        CHECK(hook_size == word && hook_quota == &alloc.free_async_space,
              "hook no longer sees padded size and live quota");
        replacement_quota = word - 1;
        result = probe(&alloc, 1, 0, 0, 1);
        CHECK(IS_ERR(result) && PTR_ERR(result) == -ENOSPC,
              "guard ignored hook-lowered quota");
        reset_hook(); alloc.mapped = false;
        result = probe(&alloc, 0, 0, 0, 1);
        CHECK(IS_ERR(result) && PTR_ERR(result) == -ESRCH && !hook_calls,
              "uninitialized allocator validation changed");
    } else return 2;
    return 0;
}
'''


class BinderAsyncQuotaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SOURCE.read_text()
        start = source.index('static struct binder_buffer *binder_alloc_new_buf_locked(')
        stop = source.index('\n\twhile (n) {', start)
        # Preserve the real declarations, VMA check, arithmetic, padding, vendor
        # hook and quota guard. Only the unrelated allocation suffix is stubbed.
        cls.helper = source[start:stop] + '\n\treturn &success;\n}\n'
        if cls.helper.count(GUARD) != 1:
            raise AssertionError('Required production quota guard is absent or ambiguous')
        cls.directory = tempfile.TemporaryDirectory(prefix='binder-async-quota-')
        try:
            cls.binary = cls.compile(cls.helper, 'fixed')
            cls.legacy = cls.compile(cls.helper.replace(GUARD, LEGACY_GUARD, 1), 'legacy')
        except BaseException:
            cls.directory.cleanup()
            raise

    @classmethod
    def compile(cls, helper, name):
        executable = Path(cls.directory.name) / name
        source = executable.with_suffix('.c')
        source.write_text(PREFIX + helper + SUFFIX)
        result = subprocess.run([
            os.environ.get('CC', 'cc'), '-std=gnu11', '-O1', '-g',
            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
            '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
            '-Wall', '-Wextra', '-Wno-unused-variable', '-Wno-unused-parameter',
            str(source), '-o', str(executable),
        ], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return executable

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_scenario(self, scenario, binary=None):
        return subprocess.run([str(binary or self.binary), str(scenario)],
                              capture_output=True, text=True, timeout=10)

    def assert_scenario(self, scenario):
        result = self.run_scenario(scenario)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exact_quota_and_residual_band_with_negative_control(self):
        self.assert_scenario(0)
        original = self.run_scenario(0, self.legacy)
        self.assertEqual(original.returncode, 1, original.stdout + original.stderr)
        self.assertIn('guard rejected usable quota', original.stderr)

    def test_shortage_synchronous_and_ordinary_quota_controls(self):
        self.assert_scenario(1)
        original = self.run_scenario(1, self.legacy)
        self.assertEqual(original.returncode, 0, original.stdout + original.stderr)

    def test_empty_parcels_and_individual_alignment(self):
        self.assert_scenario(2)
        original = self.run_scenario(2, self.legacy)
        self.assertEqual(original.returncode, 1, original.stdout + original.stderr)
        self.assertIn('empty parcel padding/quota incorrect', original.stderr)

    def test_overflow_validation_before_hook(self):
        self.assert_scenario(3)

    def test_live_vendor_hook_quota_and_uninitialized_allocator(self):
        self.assert_scenario(4)


if __name__ == '__main__':
    unittest.main()
