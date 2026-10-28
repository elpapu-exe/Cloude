#!/usr/bin/env python3
"""Compile actual reclaim/lookaround helpers with deterministic host fixtures.

The lower-level page locks, VMAs and reclaim outcomes are modeled. These are
regression tests for the production control flow, not hardware or kernel stress
reproductions of the reported bugs.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
from source_path import SOURCE_ROOT

SOURCE = SOURCE_ROOT / 'mm/vmscan.c'


def function(source, name):
    declaration = r'^(?:static )?(?:inline )?(?:enum \w+|unsigned long|unsigned int|bool|int|void)[ \t*]+'
    match = re.search(declaration + re.escape(name) + r'\([^;]*?\)\n\{', source, re.M)
    if not match:
        raise AssertionError('Missing production function: ' + name)
    cursor, depth = match.end(), 1
    while depth:
        depth += (source[cursor] == '{') - (source[cursor] == '}')
        cursor += 1
    return source[match.start():cursor]


PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); return 1; } } while (0)
#define BIT(n) (1UL << (n))
#define PG_active 0
#define LRU_REFS_MASK BIT(1)
#define LRU_REFS_FLAGS BIT(2)
#define LRU_GEN_ANON 0
#define MIN_NR_GENS 2
#define MIN_LRU_BATCH 64
#define PAGEVEC_SIZE 15
#define PAGE_SIZE 4096UL
#define PMD_MASK (~(512UL * PAGE_SIZE - 1))
#define BITS_TO_LONGS(n) (((n) + 63) / 64)
#define DEFINE_MAX_SEQ(lruvec) unsigned long max_seq = (lruvec)->lrugen.max_seq
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define pr_debug(...) ((void)0)
#define VM_IO 0x00004000UL
#define VM_DONTEXPAND 0x00040000UL
#define VM_PFNMAP 0x00000400UL
#define VM_MIXEDMAP 0x10000000UL
#define VM_SPECIAL (VM_IO | VM_DONTEXPAND | VM_PFNMAP | VM_MIXEDMAP)
#define VM_READ 1UL
struct list_head { struct list_head *next, *prev; };
#define LIST_HEAD(name) struct list_head name = { &(name), &(name) }
#define INIT_LIST_HEAD(h) do { (h)->next=(h); (h)->prev=(h); } while (0)
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
#define list_entry(ptr,type,member) container_of(ptr,type,member)
#define list_for_each_entry_safe_reverse(pos,nextpos,head,member) \
    for (pos=list_entry((head)->prev,typeof(*pos),member), \
         nextpos=list_entry(pos->member.prev,typeof(*pos),member); \
         &pos->member!=(head); \
         pos=nextpos,nextpos=list_entry(nextpos->member.prev,typeof(*nextpos),member))
static bool list_empty(struct list_head *h) { return h->next==h; }
static void list_del(struct list_head *entry) { entry->next->prev=entry->prev; entry->prev->next=entry->next; }
static void list_add_tail(struct list_head *entry, struct list_head *head) {
    entry->prev=head->prev;entry->next=head;head->prev->next=entry;head->prev=entry;
}
static void list_move(struct list_head *entry, struct list_head *head) {
    list_del(entry);entry->next=head->next;entry->prev=head;head->next->prev=entry;head->next=entry;
}
static void list_splice_init(struct list_head *from, struct list_head *to) {
    if (list_empty(from)) return;
    struct list_head *first=from->next,*last=from->prev,*old=to->next;
    to->next=first;first->prev=to;last->next=old;old->prev=last;INIT_LIST_HEAD(from);
}
struct page { struct list_head lru; unsigned long flags; unsigned int pages; int id;
    bool reclaim,dirty,writeback,workingset,active,referenced,mapped,locked,unevictable,lru_flag; };
struct mem_cgroup { int unused; };
struct pglist_data { int unused; };
struct lru_gen_struct { unsigned long max_seq; };
struct lruvec { int lru_lock; struct lru_gen_struct lrugen; };
struct lru_gen_mm_walk { unsigned int batched; };
struct reclaim_state { struct lru_gen_mm_walk *mm_walk; };
struct scan_control { unsigned long nr_scanned,nr_reclaimed; };
struct reclaim_stat { int unused; };
struct task_struct { struct reclaim_state *reclaim_state; };
static struct reclaim_state state;
static struct task_struct task={.reclaim_state=&state}, *current=&task;
static struct mem_cgroup memcg;
static struct pglist_data pgdat;
static struct lruvec lv={.lrugen={.max_seq=3}};
static int scenario,shrink_calls,putback_pages,returned_pages,hook_calls,lock_depth;
static int pte_reads,special_warnings,cleared_young,contended,ptl_locked=1;
static struct page pages[3];
static struct mem_cgroup *lruvec_memcg(struct lruvec *v) { (void)v;return &memcg; }
static struct pglist_data *lruvec_pgdat(struct lruvec *v) { (void)v;return &pgdat; }
static void spin_lock_irq(int *lock) { (void)lock;assert(lock_depth==0);lock_depth++; }
static void spin_unlock_irq(int *lock) { (void)lock;assert(lock_depth==1);lock_depth--; }
static int thp_nr_pages(struct page *p) { return p->pages; }
static bool PageReclaim(struct page *p) { return p->reclaim; }
static bool PageDirty(struct page *p) { return p->dirty; }
static bool PageWriteback(struct page *p) { return p->writeback; }
static bool PageWorkingset(struct page *p) { return p->workingset; }
static bool PageActive(struct page *p) { return p->active; }
static bool PageReferenced(struct page *p) { return p->referenced; }
static bool PageLocked(struct page *p) { return p->locked; }
static bool PageLRU(struct page *p) { return p->lru_flag; }
static bool page_mapped(struct page *p) { return p->mapped; }
static bool page_evictable(struct page *p) { return !p->unevictable; }
static void SetPageReferenced(struct page *p) { p->referenced=true; }
static void set_mask_bits(unsigned long *p,unsigned long clear,unsigned long set) { *p=(*p&~clear)|set; }
static void trace_android_vh_evict_pages_bypass(struct page *p,bool *bypass) {
    hook_calls++;if (scenario==4 && p->id==2) *bypass=true;
}
static void putback_lru_page(struct page *p) { putback_pages+=p->pages; }
static bool current_is_kswapd(void) { return false; }
static bool cgroup_reclaim(struct scan_control *sc) { (void)sc;return false; }
enum vm_event_item { PGSTEAL_KSWAPD,PGSTEAL_DIRECT,PGSTEAL_ANON };
static void __count_vm_events(enum vm_event_item i,int n) { (void)i;(void)n; }
static void __count_memcg_events(struct mem_cgroup *m,enum vm_event_item i,int n) { (void)m;(void)i;(void)n; }
static void reset_batch_size(struct lruvec *v,struct lru_gen_mm_walk *w) { (void)v;(void)w;abort(); }
static void mem_cgroup_uncharge_list(struct list_head *h) { assert(list_empty(h)); }
static void free_unref_page_list(struct list_head *h) { assert(list_empty(h)); }
static void move_pages_to_lru(struct lruvec *v,struct list_head *h) {
    (void)v;assert(lock_depth==1);
    while (!list_empty(h)) { struct page *p=list_entry(h->next,struct page,lru);list_del(&p->lru);returned_pages+=p->pages; }
}
static int isolate_pages(struct lruvec *v,struct scan_control *sc,int swappiness,int *type,struct list_head *list) {
    (void)v;(void)sc;(void)swappiness;assert(lock_depth==1);*type=LRU_GEN_ANON;
    if (scenario==3) return 0;
    for (int i=0;i<3;i++) {
        pages[i].id=i;pages[i].pages=(scenario==2 && i==1)?512:1;
        list_add_tail(&pages[i].lru,list);
    }
    return scenario==2?514:3;
}
static int try_to_inc_min_seq(struct lruvec *v,int swappiness) { (void)v;(void)swappiness;return 0; }
static int get_nr_gens(struct lruvec *v,int type) { (void)v;(void)type;return 4; }
static int shrink_page_list(struct list_head *list,struct pglist_data *p,struct scan_control *sc,struct reclaim_stat *s,bool ignore) {
    (void)p;(void)s;(void)ignore;assert(lock_depth==0);shrink_calls++;
    struct list_head *node=list->next;
    int reclaimed=0;
    while (node!=list) {
        struct page *page=list_entry(node,struct page,lru);node=node->next;
        if (scenario==1) {
            /* First page reclaimed; two trylock failures subsequently unlock.
             * On the retry both fail trylock again, so neither increments scan. */
            if (shrink_calls==1 && page->id==0) { sc->nr_scanned++;reclaimed++;list_del(&page->lru); }
            else page->locked=shrink_calls>1;
        } else if (scenario==2) {
            sc->nr_scanned+=page->pages;
            if (page->id!=1 || shrink_calls>1) { reclaimed+=page->pages;list_del(&page->lru); }
        } else if (scenario==4) {
            sc->nr_scanned+=page->pages;
            if (page->id==0) page->unevictable=true;
            else if (page->id==1) page->reclaim=page->dirty=page->workingset=true;
        } else abort();
    }
    return reclaimed;
}
enum vmpressure_levels { VMPRESSURE_LOW,VMPRESSURE_MEDIUM,VMPRESSURE_CRITICAL };
static enum vmpressure_levels vmpressure_level(unsigned long p) { return p>=95?VMPRESSURE_CRITICAL:p>=60?VMPRESSURE_MEDIUM:VMPRESSURE_LOW; }
struct vm_area_struct { unsigned long vm_start,vm_end,vm_flags; };
typedef struct { unsigned long pfn;bool present,special,young,dirty; } pte_t;
struct page_vma_mapped_walk { struct page *page;int *ptl;struct vm_area_struct *vma;unsigned long address;pte_t *pte;void *pmd; };
#define lockdep_assert_held(lock) assert(*(lock))
#define VM_WARN_ON_ONCE_PAGE(condition,page) assert(!(condition))
#define VM_WARN_ON_ONCE(condition) assert(!(condition))
#define WARN_ON_ONCE(condition) warn_once(condition)
static bool warn_once(bool condition) { if (condition) special_warnings++;return condition; }
static bool spin_is_contended(int *lock) { (void)lock;return contended; }
static int page_is_file_lru(struct page *p) { (void)p;return 0; }
static struct mem_cgroup *page_memcg(struct page *p) { (void)p;return &memcg; }
static struct pglist_data *page_pgdat(struct page *p) { (void)p;return &pgdat; }
static struct lruvec *mem_cgroup_lruvec(struct mem_cgroup *m,struct pglist_data *p) { (void)m;(void)p;return &lv; }
static int lru_gen_from_seq(unsigned long seq) { return seq%4; }
static unsigned long pte_pfn(pte_t p) { pte_reads++;return p.pfn; }
static bool pte_present(pte_t p) { return p.present; }
static bool pte_special(pte_t p) { return p.special; }
static bool pte_devmap(pte_t p) { (void)p;return false; }
static bool pfn_valid(unsigned long p) { return p==1; }
static bool is_zero_pfn(unsigned long p) { return p==0; }
static bool pte_young(pte_t p) { return p.young; }
static bool pte_dirty(pte_t p) { return p.dirty; }
static void rcu_read_lock(void) {}
static void rcu_read_unlock(void) {}
static void arch_enter_lazy_mmu_mode(void) {}
static void arch_leave_lazy_mmu_mode(void) {}
static struct page *get_pfn_page(unsigned long p,struct mem_cgroup *m,struct pglist_data *d,bool swap) { (void)p;(void)m;(void)d;(void)swap;return &pages[0]; }
static bool ptep_test_and_clear_young(struct vm_area_struct *v,unsigned long addr,pte_t *p) { (void)v;(void)addr;bool old=p->young;p->young=false;cleared_young++;return old; }
static bool PageAnon(struct page *p) { (void)p;return true; }
static bool PageSwapBacked(struct page *p) { (void)p;return true; }
static bool PageSwapCache(struct page *p) { (void)p;return false; }
static void set_page_dirty(struct page *p) { p->dirty=true; }
static int page_lru_gen(struct page *p) { (void)p;return -1; }
static void __set_bit(unsigned int bit,unsigned long *map) { map[bit/64]|=1UL<<(bit%64); }
static unsigned int bitmap_weight(unsigned long *map,unsigned int n) { unsigned int total=0;for(unsigned int i=0;i<n;i++)total+=!!(map[i/64]&(1UL<<(i%64)));return total; }
#define for_each_set_bit(i,map,n) for ((i)=0;(i)<(n);(i)++) if ((map)[(i)/64]&(1UL<<((i)%64)))
static bool suitable_to_scan(int scanned,int young) { (void)scanned;(void)young;return false; }
static void update_bloom_filter(struct lruvec *v,unsigned long seq,void *pmd) { (void)v;(void)seq;(void)pmd;abort(); }
static struct page *pte_page(pte_t p) { (void)p;return &pages[0]; }
static void activate_page(struct page *p) { (void)p;abort(); }
static bool mem_cgroup_trylock_pages(struct mem_cgroup *m) { (void)m;abort(); }
static void mem_cgroup_unlock_pages(void) { abort(); }
static struct page *compound_head(struct page *p) { return p; }
static struct mem_cgroup *page_memcg_rcu(struct page *p) { (void)p;return &memcg; }
static int page_update_gen(struct page *p,int gen,int *type) { (void)p;(void)gen;(void)type;abort(); }
static void update_batch_size(struct lru_gen_mm_walk *w,struct page *p,int old,int new,int type) { (void)w;(void)p;(void)old;(void)new;(void)type;abort(); }
static void lru_gen_update_size(struct lruvec *v,struct page *p,int old,int new) { (void)v;(void)p;(void)old;(void)new;abort(); }
'''

SUFFIX = r'''
int main(int argc,char **argv) {
    assert(argc==2);scenario=atoi(argv[1]);
    if (scenario<10) {
        struct scan_control sc={0};bool swapping=false;
        int scanned=evict_pages(&lv,&sc,100,&swapping);
        if (scenario==1) {
            /* Evaluate the actual production pressure function before checking
             * counters: the old subtraction must trip UBSan's division check. */
            CHECK(vmpressure_calc_level(sc.nr_scanned,sc.nr_reclaimed)==VMPRESSURE_LOW);
            CHECK(sc.nr_scanned==1 && sc.nr_reclaimed==1);
            CHECK(shrink_calls==2 && returned_pages==2 && hook_calls==4);
            CHECK(swapping && scanned==3 && lock_depth==0);
        } else if (scenario==2) {
            CHECK(shrink_calls==2 && sc.nr_scanned==1026 && sc.nr_reclaimed==514);
            CHECK(returned_pages==0 && hook_calls==1 && swapping);
        } else if (scenario==3) {
            CHECK(!scanned && !sc.nr_scanned && !sc.nr_reclaimed && !shrink_calls && !swapping && !hook_calls);
        } else if (scenario==4) {
            CHECK(shrink_calls==1 && sc.nr_scanned==3 && sc.nr_reclaimed==0);
            CHECK(putback_pages==1 && returned_pages==2 && hook_calls==3 && pages[1].referenced);
        } else return 2;
    } else {
        current->reclaim_state=NULL;
        struct vm_area_struct vma={.vm_start=PAGE_SIZE,.vm_end=2*PAGE_SIZE,.vm_flags=VM_READ};
        pte_t pte={.pfn=1,.present=true,.young=true};
        struct page_vma_mapped_walk pvmw={.page=&pages[0],.ptl=&ptl_locked,.vma=&vma,.address=PAGE_SIZE,.pte=&pte};
        if (scenario>=11 && scenario<=14) {
            unsigned long special[]={VM_IO,VM_DONTEXPAND,VM_PFNMAP,VM_MIXEDMAP};
            vma.vm_flags|=special[scenario-11];pte.special=true;
        } else if (scenario==15) contended=1;
        else if (scenario!=10) return 2;
        lru_gen_look_around(&pvmw);
        if (scenario==10) CHECK(pte_reads==1 && cleared_young==1 && pages[0].referenced && !special_warnings);
        else CHECK(!pte_reads && !cleared_young && !pages[0].referenced && !special_warnings);
    }
    return 0;
}
'''


class MglruReclaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='mglru-reclaim-')
        cls.source = SOURCE.read_text()
        cls.evict = function(cls.source, 'evict_pages')
        cls.look = function(cls.source, 'lru_gen_look_around')
        cls.pfn = function(cls.source, 'get_pte_pfn')
        pressure_source = (SOURCE_ROOT / 'mm/vmpressure.c').read_text()
        cls.pressure = function(pressure_source, 'vmpressure_calc_level')
        cls.binary = cls.compile(cls.evict, cls.look, 'fixed')

    @classmethod
    def compile(cls, evict, look, name):
        path = Path(cls.directory.name) / name
        path.with_suffix('.c').write_text(PREFIX + cls.pressure + '\n' + evict + '\n' + cls.pfn + '\n' + look + SUFFIX)
        result = subprocess.run([
            os.environ.get('CC', 'cc'), '-std=gnu11', '-O1', '-g',
            '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
            '-fno-omit-frame-pointer', '-fno-pie', '-no-pie', '-Wall', '-Wextra',
            '-Wno-unused-function', str(path.with_suffix('.c')), '-o', str(path)
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

    def test_trylock_retry_does_not_underflow_or_divide_by_zero(self):
        self.assert_scenario(1)
        anchor = '\t\tlist_move(&page->lru, &clean);\n'
        self.assertEqual(self.evict.count(anchor), 1)
        mutant = self.evict.replace(anchor, anchor + '\t\tsc->nr_scanned -= thp_nr_pages(page);\n')
        baseline = self.compile(mutant, self.look, 'negative-old-subtraction')
        result = self.run_scenario(1, baseline)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('division by zero', result.stderr)

    def test_successful_retry_keeps_monotonic_scan_accounting(self):
        self.assert_scenario(2)

    def test_empty_isolation_retains_fast_return(self):
        self.assert_scenario(3)

    def test_rejections_and_vendor_bypass_keep_existing_behavior(self):
        self.assert_scenario(4)

    def test_special_vmas_are_not_walked(self):
        guard = '\tif (pvmw->vma->vm_flags & VM_SPECIAL)\n\t\treturn;\n'
        self.assertEqual(self.look.count(guard), 1)
        baseline = self.compile(self.evict, self.look.replace(guard, ''), 'negative-missing-vma-guard')
        for scenario in range(11, 15):
            with self.subTest(scenario=scenario):
                self.assert_scenario(scenario)
                result = self.run_scenario(scenario, baseline)
                self.assertNotEqual(result.returncode, 0, 'Baseline did not expose special-PTE walk')

    def test_normal_vma_and_contended_ptl_retain_behavior(self):
        self.assert_scenario(10)
        self.assert_scenario(15)


if __name__ == '__main__':
    unittest.main()
