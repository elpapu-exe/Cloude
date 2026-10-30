#!/usr/bin/env python3
"""Run production reclaim helpers with CMA-heavy lists under ASan/UBSan.

These deterministic host tests check admission and scan counts while modelling
page/list/VM primitives. They do not measure phone latency, allocator success or
kernel lock contention. The pre-0018 fixture includes the preceding rc5 fix.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
from source_path import SOURCE_ROOT

ROOT = Path(__file__).resolve().parents[1]
SOURCE = SOURCE_ROOT / 'mm/vmscan.c'
FIXTURE = ROOT / 'tests/fixtures/mglru-before-0018-cma.c'


def function(source, name):
    match = re.search(r'^(?:static )?(?:unsigned long|int|bool) ' + re.escape(name) + r'\(',
                      source, re.MULTILINE)
    if not match:
        raise AssertionError('missing production helper: ' + name)
    brace = source.index('{', match.start())
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end] + '\n'


PREFIX = r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define BIT(n) (1UL << (n))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x, value) ((x) = (value))
#define unlikely(x) (x)
#define max(a, b) ((a) > (b) ? (a) : (b))
#define MAX_NR_GENS 4
#define MIN_NR_GENS 2
#define ANON_AND_FILE 2
#define MAX_NR_ZONES 3
#define LRU_GEN_ANON 0
#define LRU_GEN_FILE 1
#define MIN_LRU_BATCH 64
#define MAX_LRU_BATCH (MIN_LRU_BATCH * 64)
#define LRU_REFS_WIDTH 2
#define LRU_REFS_MASK (3UL << 12)
#define LRU_REFS_FLAGS BIT(14)
#define MIGRATE_MOVABLE 1
#define MIGRATE_CMA 2
#define __GFP_IO 4
#define ISOLATE_UNMAPPED 1
#define VM_WARN_ON_ONCE(x) do { if (x) abort(); } while (0)
#define VM_WARN_ON_ONCE_PAGE(x, page) VM_WARN_ON_ONCE(x)
#define CHECK(x, message) do { if (!(x)) { fprintf(stderr, "%s\n", message); return 1; } } while (0)
struct list_head { struct list_head *next, *prev; };
#define LIST_HEAD(name) struct list_head name = { &(name), &(name) }
#define container_of(pointer, type, member) ((type *)((char *)(pointer) - offsetof(type, member)))
#define lru_to_page(head) container_of((head)->prev, struct page, lru)
static void INIT_LIST_HEAD(struct list_head *head) { head->next = head->prev = head; }
static bool list_empty(const struct list_head *head) { return head->next == head; }
static void list_add(struct list_head *node, struct list_head *head)
{
    node->next = head->next; node->prev = head;
    head->next->prev = node; head->next = node;
}
static void list_add_tail(struct list_head *node, struct list_head *head)
{
    node->next = head; node->prev = head->prev;
    head->prev->next = node; head->prev = node;
}
static void list_del(struct list_head *node)
{
    node->next->prev = node->prev; node->prev->next = node->next;
    INIT_LIST_HEAD(node);
}
static void list_move(struct list_head *node, struct list_head *head) { list_del(node); list_add(node, head); }
static void list_move_tail(struct list_head *node, struct list_head *head) { list_del(node); list_add_tail(node, head); }
static void list_splice(struct list_head *list, struct list_head *head)
{
    if (list_empty(list)) return;
    struct list_head *first = list->next, *last = list->prev, *next = head->next;
    first->prev = head; head->next = first; last->next = next; next->prev = last;
}
enum lru_list { LRU_INACTIVE_FILE, LRU_OTHER, NR_LRU_LISTS };
enum vm_event_item { UNEVICTABLE_PGCULLED, PGSCAN_SKIP, PGSCAN_KSWAPD, PGSCAN_DIRECT,
                     PGREFILL, PGSCAN_ANON, PGSCAN_FILE, NR_EVENTS };
enum { F_LRU, F_ACTIVE, F_UNEVICTABLE, F_DIRTY, F_LOCKED, F_WRITEBACK,
       F_ANON, F_SWAPCACHE, F_REFERENCED, F_RECLAIM, F_SWAPBACKED };
struct page {
    struct list_head lru;
    unsigned long flags;
    int zone, type, gen, refs, pages, migratetype, refcount;
    bool mapped, evictable, fail_clear_lru;
};
struct lru_gen_struct {
    struct list_head lists[MAX_NR_GENS][ANON_AND_FILE][MAX_NR_ZONES];
    unsigned long min_seq[ANON_AND_FILE];
    unsigned long protected[MAX_NR_GENS][ANON_AND_FILE][4];
    int nr_gens;
};
struct lruvec { struct list_head lists[NR_LRU_LISTS]; struct lru_gen_struct lrugen; };
struct scan_control { int reclaim_idx, order, gfp_mask; bool may_unmap, may_writepage, cgroup; };
struct mem_cgroup { int unused; };
static bool kswapd;
static unsigned long visits, increments, reclaim_increments, hooks, events[NR_EVENTS], zones[MAX_NR_ZONES], taken[MAX_NR_ZONES];
static bool current_is_kswapd(void) { return kswapd; }
static int gfp_migratetype(int mask) { return mask & MIGRATE_MOVABLE; }
static int get_pageblock_migratetype(struct page *page) { return page->migratetype; }
static int page_zonenum(struct page *page) { return page->zone; }
static int compound_nr(struct page *page) { return page->pages; }
static int thp_nr_pages(struct page *page) { visits++; return page->pages; }
static int page_lru_gen(struct page *page) { return page->gen; }
static int page_lru_refs(struct page *page) { return page->refs; }
static int page_is_file_lru(struct page *page) { return page->type; }
static int lru_tier_from_refs(int refs) { return refs ? (refs >= 4 ? 2 : 1) : 0; }
static int lru_gen_from_seq(unsigned long seq) { return seq % MAX_NR_GENS; }
static int lru_hist_from_seq(unsigned long seq) { return seq % MAX_NR_GENS; }
static bool page_evictable(struct page *page) { return page->evictable; }
static bool page_mapped(struct page *page) { return page->mapped; }
#define FLAG(name, flag) static bool Page##name(struct page *page) { return !!(page->flags & BIT(flag)); }
FLAG(LRU, F_LRU) FLAG(Active, F_ACTIVE) FLAG(Unevictable, F_UNEVICTABLE)
FLAG(Dirty, F_DIRTY) FLAG(Locked, F_LOCKED) FLAG(Writeback, F_WRITEBACK)
FLAG(Anon, F_ANON) FLAG(SwapCache, F_SWAPCACHE) FLAG(Referenced, F_REFERENCED)
static void SetPageUnevictable(struct page *page) { page->flags |= BIT(F_UNEVICTABLE); }
static void SetPageSwapBacked(struct page *page) { page->flags |= BIT(F_SWAPBACKED); }
static void ClearPageReclaim(struct page *page) { page->flags &= ~BIT(F_RECLAIM); }
static void ClearPageReferenced(struct page *page) { page->flags &= ~BIT(F_REFERENCED); }
static bool get_page_unless_zero(struct page *page) { if (!page->refcount) return false; page->refcount++; return true; }
static void put_page(struct page *page) { page->refcount--; }
static bool TestClearPageLRU(struct page *page)
{
    bool old = PageLRU(page); page->flags &= ~BIT(F_LRU);
    return page->fail_clear_lru ? false : old;
}
static void set_mask_bits(unsigned long *flags, unsigned long mask, unsigned long bits) { *flags = (*flags & ~mask) | bits; }
static bool lru_gen_del_page(struct lruvec *lruvec, struct page *page, bool reclaiming)
{ (void)lruvec; (void)reclaiming; list_del(&page->lru); page->gen = -1; return true; }
static int page_inc_gen(struct lruvec *lruvec, struct page *page, bool reclaiming)
{
    (void)lruvec; increments++; reclaim_increments += reclaiming;
    page->gen = (page->gen + 1) % MAX_NR_GENS; return page->gen;
}
static void add_page_to_lru_list(struct page *page, struct lruvec *lruvec) { list_add(&page->lru, &lruvec->lists[LRU_OTHER]); }
static void add_page_to_lru_list_tail(struct page *page, struct lruvec *lruvec) { list_add_tail(&page->lru, &lruvec->lists[LRU_OTHER]); }
#define prefetchw_prev_lru_page(page, head, member) do {} while (0)
static void trace_android_vh_del_page_from_lrulist(struct page *page, bool reclaiming, enum lru_list lru)
{ (void)page; (void)reclaiming; (void)lru; hooks++; }
static void trace_mm_vmscan_lru_isolate(int idx, int order, unsigned long request,
    unsigned long scanned, unsigned long skipped, unsigned long isolated, int mode, enum lru_list lru)
{ (void)idx; (void)order; (void)request; (void)scanned; (void)skipped; (void)isolated; (void)mode; (void)lru; }
static void update_lru_sizes(struct lruvec *lruvec, enum lru_list lru, unsigned long *counts)
{ (void)lruvec; (void)lru; memcpy(taken, counts, sizeof(taken)); }
static void __count_vm_events(enum vm_event_item item, unsigned long count) { events[item] += count; }
static void __count_zid_vm_events(enum vm_event_item item, int zone, unsigned long count) { (void)item; zones[zone] += count; }
static void __count_memcg_events(struct mem_cgroup *memcg, enum vm_event_item item, unsigned long count) { (void)memcg; (void)item; (void)count; }
static bool cgroup_reclaim(struct scan_control *sc) { return sc->cgroup; }
static struct mem_cgroup *lruvec_memcg(struct lruvec *lruvec) { (void)lruvec; return NULL; }
static int get_nr_gens(struct lruvec *lruvec, int type) { (void)type; return lruvec->lrugen.nr_gens; }
'''

SUFFIX = r'''
static void init(struct lruvec *lruvec)
{
    memset(lruvec, 0, sizeof(*lruvec));
    for (int i = 0; i < NR_LRU_LISTS; i++) INIT_LIST_HEAD(&lruvec->lists[i]);
    for (int gen = 0; gen < MAX_NR_GENS; gen++)
        for (int type = 0; type < ANON_AND_FILE; type++)
            for (int zone = 0; zone < MAX_NR_ZONES; zone++)
                INIT_LIST_HEAD(&lruvec->lrugen.lists[gen][type][zone]);
    lruvec->lrugen.nr_gens = MAX_NR_GENS;
    visits = increments = reclaim_increments = hooks = 0;
    memset(events, 0, sizeof(events)); memset(zones, 0, sizeof(zones)); memset(taken, 0, sizeof(taken));
}
static struct page make_page(void)
{
    struct page page = { .flags = BIT(F_LRU), .zone = 1, .type = LRU_GEN_FILE,
                        .pages = 1, .migratetype = MIGRATE_CMA, .refcount = 1, .evictable = true };
    return page;
}
static struct page *populate(struct lruvec *lruvec, int nr, bool mglru, bool cma)
{
    struct page *pages = calloc(nr, sizeof(*pages));
    if (!pages) abort();
    for (int i = 0; i < nr; i++) {
        pages[i] = make_page(); pages[i].migratetype = cma ? MIGRATE_CMA : 0;
        struct list_head *head = mglru ? &lruvec->lrugen.lists[0][LRU_GEN_FILE][1] : &lruvec->lists[LRU_INACTIVE_FILE];
        list_add(&pages[i].lru, head); /* The kernel scans the tail, oldest first. */
    }
    return pages;
}
static int list_count(struct list_head *head)
{
    int count = 0;
    for (struct list_head *p = head->next; p != head; p = p->next) {
        if (++count > 20000) abort();
        if (p->next->prev != p || p->prev->next != p) abort();
    }
    return count;
}
int main(int argc, char **argv)
{
    CHECK(argc == 2, "missing scenario");
    struct lruvec lruvec;
    struct scan_control sc = { .reclaim_idx = 1, .gfp_mask = __GFP_IO, .may_unmap = true, .may_writepage = true };
    LIST_HEAD(output);
    int scenario = atoi(argv[1]);
    init(&lruvec);
    if (scenario == 0) {
        const int nr = MAX_LRU_BATCH * 2;
        struct page *pages = populate(&lruvec, nr, false, true);
        unsigned long scanned = 0;
        unsigned long isolated = isolate_lru_pages(MIN_LRU_BATCH, &lruvec, &output, &scanned, &sc, LRU_INACTIVE_FILE);
        CHECK(scanned == MIN_LRU_BATCH && hooks == MIN_LRU_BATCH, "classic CMA scan exceeded requested batch");
        CHECK(isolated == MIN_LRU_BATCH && list_count(&output) == MIN_LRU_BATCH, "classic CMA pages were skipped");
        CHECK(taken[1] == MIN_LRU_BATCH && !zones[1], "classic CMA accounting changed");
        free(pages);
    } else if (scenario == 1) {
        struct page pages[2] = { make_page(), make_page() };
        pages[0].zone = 2; pages[0].migratetype = 0; pages[0].pages = 8;
        pages[1].migratetype = 0; pages[1].pages = 8;
        list_add(&pages[0].lru, &lruvec.lists[LRU_INACTIVE_FILE]);
        list_add(&pages[1].lru, &lruvec.lists[LRU_INACTIVE_FILE]);
        unsigned long scanned = 0;
        CHECK(isolate_lru_pages(4, &lruvec, &output, &scanned, &sc, LRU_INACTIVE_FILE) == 8, "classic THP isolation changed");
        CHECK(scanned == 16 && zones[2] == 8 && taken[1] == 8, "classic zone/THP filtering changed");
        for (int gate = 0; gate < 4; gate++) {
            init(&lruvec); INIT_LIST_HEAD(&output);
            struct page page = make_page(); page.migratetype = 0;
            if (gate == 0) { page.mapped = true; sc.may_unmap = false; }
            if (gate == 1) page.refcount = 0;
            if (gate == 2) page.flags &= ~BIT(F_LRU);
            if (gate == 3) page.fail_clear_lru = true;
            list_add(&page.lru, &lruvec.lists[LRU_INACTIVE_FILE]);
            CHECK(isolate_lru_pages(1, &lruvec, &output, &scanned, &sc, LRU_INACTIVE_FILE) == 0, "classic eligibility gate bypassed");
            CHECK(scanned == 1 && list_empty(&output), "classic gate scan contract changed");
            sc.may_unmap = true;
        }
    } else if (scenario == 2) {
        struct page *pages = populate(&lruvec, MAX_LRU_BATCH * 2, true, true);
        int scanned = scan_pages(&lruvec, &sc, LRU_GEN_FILE, 0, &output);
        CHECK(scanned == MIN_LRU_BATCH && list_count(&output) == MIN_LRU_BATCH, "MGLRU CMA scan failed to isolate a bounded batch");
        CHECK(!increments && !events[PGREFILL], "CMA pages spuriously promoted");
        CHECK(events[PGSCAN_DIRECT] == MIN_LRU_BATCH && events[PGSCAN_FILE] == MIN_LRU_BATCH, "MGLRU CMA scan accounting changed");
        CHECK(pages[MIN_LRU_BATCH].gen == 0, "unscanned generation changed");
        free(pages);
    } else if (scenario == 3) {
        /* Existing zone/writeback/protection/unmapping gates must survive. */
        kswapd = true; /* Also permits comparing unchanged gates with the fixture. */
        struct page page = make_page(); page.zone = 2;
        list_add(&page.lru, &lruvec.lrugen.lists[0][LRU_GEN_FILE][2]);
        CHECK(sort_page(&lruvec, &page, &sc, 0) && page.gen == 1, "MGLRU zone filter removed");
        for (int gate = 0; gate < 5; gate++) {
            init(&lruvec); page = make_page();
            if (gate == 0) page.flags |= BIT(F_LOCKED);
            if (gate == 1) page.flags |= BIT(F_WRITEBACK);
            if (gate == 2) page.flags |= BIT(F_DIRTY);
            if (gate == 3) { page.refs = 2; }
            if (gate == 4) page.evictable = false;
            list_add(&page.lru, &lruvec.lrugen.lists[0][LRU_GEN_FILE][1]);
            CHECK(sort_page(&lruvec, &page, &sc, 0), "MGLRU existing sort gate bypassed");
            if (gate < 3) CHECK(page.gen == 1 && reclaim_increments == 1, "writeback generation behavior changed");
            if (gate == 3) CHECK(lruvec.lrugen.protected[0][LRU_GEN_FILE][0] == 1, "protection accounting changed");
            if (gate == 4) CHECK(PageUnevictable(&page), "unevictable page not preserved");
        }
        for (int gate = 0; gate < 5; gate++) {
            init(&lruvec); page = make_page();
            sc.may_unmap = sc.may_writepage = true; sc.gfp_mask = __GFP_IO;
            if (gate == 0) { page.mapped = true; sc.may_unmap = false; }
            if (gate == 1) { page.flags |= BIT(F_ANON); sc.may_writepage = false; }
            if (gate == 2) { page.flags |= BIT(F_ANON); sc.gfp_mask = 0; }
            if (gate == 3) page.refcount = 0;
            if (gate == 4) page.fail_clear_lru = true;
            CHECK(!isolate_page(&lruvec, &page, &sc), "MGLRU isolation gate bypassed");
            CHECK(page.refcount == (gate == 3 ? 0 : 1), "MGLRU failed-isolation reference leaked");
        }
    } else if (scenario == 4) {
        for (int context = 0; context < 2; context++) {
            kswapd = context == 0; sc.gfp_mask = __GFP_IO | (context == 1 ? MIGRATE_MOVABLE : 0);
            init(&lruvec); INIT_LIST_HEAD(&output);
            struct page *pages = populate(&lruvec, MAX_LRU_BATCH * 2, false, true);
            unsigned long scanned = 0;
            CHECK(isolate_lru_pages(MIN_LRU_BATCH, &lruvec, &output, &scanned, &sc, LRU_INACTIVE_FILE) == MIN_LRU_BATCH && scanned == MIN_LRU_BATCH,
                  "kswapd/movable classic control changed");
            free(pages); init(&lruvec); INIT_LIST_HEAD(&output);
            pages = populate(&lruvec, MAX_LRU_BATCH * 2, true, true);
            CHECK(scan_pages(&lruvec, &sc, LRU_GEN_FILE, 0, &output) == MIN_LRU_BATCH && list_count(&output) == MIN_LRU_BATCH,
                  "kswapd/movable MGLRU control changed");
            free(pages);
        }
    } else if (scenario == 5) {
        struct page *pages = populate(&lruvec, MAX_LRU_BATCH * 2, true, true);
        sc.may_unmap = false;
        for (int i = 0; i < MAX_LRU_BATCH * 2; i++) pages[i].mapped = true;
        CHECK(scan_pages(&lruvec, &sc, LRU_GEN_FILE, 0, &output) == 0, "mapped-only scan falsely reports progress");
        CHECK(list_empty(&output) && zones[1] == MIN_LRU_BATCH, "mapped-only skip bound changed");
        free(pages); init(&lruvec); INIT_LIST_HEAD(&output); sc.may_unmap = true;
        pages = populate(&lruvec, MAX_LRU_BATCH * 2, true, true);
        /* Put them in the higher zone's list to check MAX_LRU_BATCH remains. */
        for (int i = 0; i < MAX_LRU_BATCH * 2; i++) {
            list_del(&pages[i].lru); pages[i].zone = 2;
            list_add(&pages[i].lru, &lruvec.lrugen.lists[0][LRU_GEN_FILE][2]);
        }
        CHECK(scan_pages(&lruvec, &sc, LRU_GEN_FILE, 0, &output) == MAX_LRU_BATCH && list_empty(&output),
              "higher-zone scan lost its maximum batch bound");
        CHECK(increments == MAX_LRU_BATCH, "higher-zone promotion contract changed");
        free(pages);
    } else return 2;
    return 0;
}
'''


class MglruCmaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SOURCE.read_text()
        if 'skip_cma(' in source:
            raise AssertionError('CMA skip helper/calls remain in current source')
        cls.directory = tempfile.TemporaryDirectory(prefix='mglru-cma-')
        helpers = ''.join(function(source, name) for name in
                          ('isolate_lru_pages', 'sort_page', 'isolate_page', 'scan_pages'))
        old_helpers = FIXTURE.read_text() + function(source, 'isolate_page') + function(source, 'scan_pages')
        try:
            cls.binary = cls.compile(helpers, 'current')
            cls.previous = cls.compile(old_helpers, 'previous')
        except BaseException:
            cls.directory.cleanup()
            raise

    @classmethod
    def compile(cls, helpers, name):
        executable = Path(cls.directory.name) / name
        source = executable.with_suffix('.c')
        source.write_text(PREFIX + helpers + SUFFIX)
        result = subprocess.run([
            os.environ.get('CC', 'cc'), '-std=gnu11', '-O1', '-g',
            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
            '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
            '-Wall', '-Wextra', '-Wno-unused-function',
            str(source), '-o', str(executable),
        ], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return executable

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_scenario(self, scenario, previous=False):
        return subprocess.run([str(self.previous if previous else self.binary), str(scenario)],
                              capture_output=True, text=True, timeout=10)

    def assert_scenario(self, scenario):
        result = self.run_scenario(scenario)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_classic_cma_heavy_list_stops_at_requested_batch(self):
        self.assert_scenario(0)
        old = self.run_scenario(0, previous=True)
        self.assertEqual(old.returncode, 1, old.stdout + old.stderr)
        self.assertIn('classic CMA scan exceeded requested batch', old.stderr)

    def test_classic_zone_thp_and_eligibility_controls(self):
        self.assert_scenario(1)
        old = self.run_scenario(1, previous=True)
        self.assertEqual(old.returncode, 0, old.stdout + old.stderr)

    def test_mglru_cma_pages_are_isolated_without_spurious_promotion(self):
        self.assert_scenario(2)
        old = self.run_scenario(2, previous=True)
        self.assertEqual(old.returncode, 1, old.stdout + old.stderr)
        self.assertIn('MGLRU CMA scan failed to isolate a bounded batch', old.stderr)

    def test_mglru_existing_zone_writeback_and_mapping_gates(self):
        self.assert_scenario(3)
        old = self.run_scenario(3, previous=True)
        self.assertEqual(old.returncode, 0, old.stdout + old.stderr)

    def test_kswapd_and_movable_allocations_remain_unchanged(self):
        self.assert_scenario(4)
        old = self.run_scenario(4, previous=True)
        self.assertEqual(old.returncode, 0, old.stdout + old.stderr)

    def test_mglru_other_ineligible_scans_keep_their_bounds(self):
        self.assert_scenario(5)


if __name__ == '__main__':
    unittest.main()
