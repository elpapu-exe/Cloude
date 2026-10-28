#!/usr/bin/env python3
"""Compile the production MGLRU helpers and inject deterministic CAS races.

The page type can change during an LRU del/add pair after the generation CAS.
These tests check the batched deltas against that CAS snapshot, including a
failed first CAS. This is a userspace helper test, not a kernel concurrency test.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "kernel-source/linux/mm/vmscan.c"


def function(source, name):
    match = re.search(r"^static [^\n]*\b" + re.escape(name), source, re.MULTILINE)
    if not match:
        raise AssertionError("missing production helper: " + name)
    start = match.start()
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


PREFIX = r'''
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define BIT(n) (1UL << (n))
#define READ_ONCE(x) (x)
#define MAX_NR_GENS 4
#define LRU_GEN_PGOFF 8
#define LRU_GEN_MASK (7UL << LRU_GEN_PGOFF)
#define LRU_REFS_MASK (3UL << 12)
#define LRU_REFS_FLAGS BIT(14)
#define PG_swapbacked 0
#define PG_referenced 1
#define VM_WARN_ON_ONCE(x) do { if (x) abort(); } while (0)
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); return 1; } } while (0)
struct page { unsigned long flags; int zone, pages; };
struct lru_gen_mm_walk { unsigned int batched; int nr_pages[4][2][3]; };
static bool rcu_read_lock_held(void) { return true; }
static int page_zonenum(struct page *p) { return p->zone; }
static int thp_nr_pages(struct page *p) { return p->pages; }
static int page_is_file_lru(struct page *p) { return !(p->flags & BIT(PG_swapbacked)); }
static int failures, attempts;
static unsigned long retry_flags, after_flags;
static bool change_after;
static unsigned long flags_for(int gen, int file)
{
    return ((gen + 1UL) << LRU_GEN_PGOFF) | (file ? 0 : BIT(PG_swapbacked));
}
static bool try_cmpxchg(unsigned long *ptr, unsigned long *old, unsigned long new)
{
    attempts++;
    if (failures) {
        failures--;
        *ptr = retry_flags;
        *old = *ptr;
        return false;
    }
    if (*ptr != *old) { *old = *ptr; return false; }
    *ptr = new;
    /* The del/add pair completes before page_update_gen reads live flags. */
    if (change_after) *ptr = after_flags;
    return true;
}
'''

SUFFIX = r'''
int main(int argc, char **argv)
{
    struct lru_gen_mm_walk walk = {0};
    struct page page = { .zone = 2, .pages = 1 };
    int type = -9, old, scenario;
    if (argc != 2) return 2;
    scenario = atoi(argv[1]);
    if (scenario == 1) {
        page.flags = flags_for(0, 0);
        change_after = true; after_flags = flags_for(0, 1);
        old = page_update_gen(&page, 3, &type);
        CHECK(old == 0 && type == 0);
        update_batch_size(&walk, &page, old, 3, type);
        CHECK(walk.batched == 1);
        CHECK(walk.nr_pages[0][0][2] == -1 && walk.nr_pages[3][0][2] == 1);
        CHECK(walk.nr_pages[0][1][2] == 0 && walk.nr_pages[3][1][2] == 0);
    } else if (scenario == 2) {
        page.flags = flags_for(1, 1); page.pages = 512;
        change_after = true; after_flags = flags_for(0, 0);
        old = page_update_gen(&page, 3, &type);
        CHECK(old == 1 && type == 1);
        update_batch_size(&walk, &page, old, 3, type);
        CHECK(walk.nr_pages[1][1][2] == -512 && walk.nr_pages[3][1][2] == 512);
        CHECK(walk.nr_pages[1][0][2] == 0 && walk.nr_pages[3][0][2] == 0);
    } else if (scenario == 3) {
        page.flags = flags_for(0, 0);
        failures = 1; retry_flags = flags_for(2, 1);
        change_after = true; after_flags = flags_for(1, 0);
        old = page_update_gen(&page, 3, &type);
        CHECK(attempts == 2 && old == 2 && type == 1);
        update_batch_size(&walk, &page, old, 3, type);
        CHECK(walk.nr_pages[2][1][2] == -1 && walk.nr_pages[3][1][2] == 1);
        CHECK(walk.nr_pages[0][0][2] == 0);
    } else if (scenario == 4) {
        page.flags = BIT(PG_swapbacked);
        old = page_update_gen(&page, 3, &type);
        CHECK(old == -1 && type == 0 && attempts == 1);
        CHECK(page.flags == (BIT(PG_swapbacked) | BIT(PG_referenced)));
        if (old >= 0 && old != 3) update_batch_size(&walk, &page, old, 3, type);
        CHECK(walk.batched == 0);
        page.flags = flags_for(3, 1); type = -9;
        old = page_update_gen(&page, 3, &type);
        if (old >= 0 && old != 3) update_batch_size(&walk, &page, old, 3, type);
        CHECK(old == 3 && type == 1 && walk.batched == 0);
    } else return 2;
    return 0;
}
'''


class MglruAccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="mglru-accounting-")
        cls.source = SOURCE.read_text()
        cls.helpers = "\n".join(function(cls.source, name) for name in (
            "page_update_gen(", "update_batch_size("))
        cls.binary = cls.compile(cls.helpers, "fixed")

    @classmethod
    def compile(cls, helpers, name):
        path = Path(cls.directory.name) / name
        path.with_suffix(".c").write_text(PREFIX + helpers + SUFFIX)
        result = subprocess.run([
            os.environ.get("CC", "cc"), "-std=gnu11", "-O1", "-g",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-fno-pie", "-no-pie", "-Wall", "-Wextra",
            "-Wno-unused-function", str(path.with_suffix(".c")), "-o", str(path)
        ], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return path

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_scenario(self, scenario, binary=None):
        return subprocess.run([str(binary or self.binary), str(scenario)],
                              capture_output=True, text=True)

    def assert_scenario(self, scenario):
        result = self.run_scenario(scenario)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_anon_to_file_after_cas(self):
        self.assert_scenario(1)
        # Reintroducing the old live-flags read must expose the race.
        mutant = self.helpers.replace(
            "int zone = page_zonenum(page);",
            "type = page_is_file_lru(page);\n\tint zone = page_zonenum(page);")
        self.assertNotEqual(mutant, self.helpers)
        binary = self.compile(mutant, "negative-live-flags")
        self.assertNotEqual(self.run_scenario(1, binary).returncode, 0)
        self.assertNotEqual(self.run_scenario(2, binary).returncode, 0)

    def test_file_to_anon_thp_after_cas(self):
        self.assert_scenario(2)

    def test_cas_retry_captures_successful_snapshot(self):
        self.assert_scenario(3)
        # Capturing the initial state, rather than the successful CAS, is wrong.
        assignment = "\t*type = !(old_flags & BIT(PG_swapbacked));\n"
        self.assertIn(assignment, self.helpers)
        mutant = self.helpers.replace(assignment, "").replace(
            "\tdo {", assignment + "\tdo {", 1)
        binary = self.compile(mutant, "negative-initial-flags")
        self.assertNotEqual(self.run_scenario(3, binary).returncode, 0)

    def test_isolated_same_generation_and_caller_contracts(self):
        self.assert_scenario(4)
        # Check all three real call sites pass the captured type through.
        self.assertEqual(self.source.count("page_update_gen(page, new_gen, &type)"), 3)
        self.assertEqual(self.source.count(
            "update_batch_size(walk, page, old_gen, new_gen, type);"), 3)
        look = self.source[self.source.index("void lru_gen_look_around("):]
        lock = look.index("spin_lock_irq(&lruvec->lru_lock)")
        direct = look.index("lru_gen_update_size(lruvec, page, old_gen, new_gen)")
        unlock = look.index("spin_unlock_irq(&lruvec->lru_lock)")
        self.assertLess(lock, direct)
        self.assertLess(direct, unlock)


if __name__ == "__main__":
    unittest.main()
