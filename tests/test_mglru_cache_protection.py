#!/usr/bin/env python3
"""Exercise real page-based MGLRU placement, sorting and refault helpers.

Production functions run with ASan/UBSan and deterministic page/list/counter
fixtures. This checks the cache-protection contracts; it is not a workload
benchmark, a kernel concurrency proof or evidence of a TAPAS speedup.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
from source_path import SOURCE_ROOT

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/mglru-rc4-cache.c'


def function(source, name):
    declaration = r'^(?:static )?(?:inline )?(?:enum \w+|unsigned long|unsigned int|bool|int|void)[ \t*]+'
    match = re.search(declaration + re.escape(name) + r'\([^;]*?\)\n\{', source, re.M)
    if not match:
        raise AssertionError('Missing production helper: ' + name)
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
#define BIT(n) (1UL << (n))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define PG_active 0
#define PG_workingset 1
#define PG_swapbacked 2
#define PG_swapcache 3
#define PG_dirty 4
#define PG_writeback 5
#define PG_reclaim 6
#define PG_unevictable 7
#define PG_anon 8
#define PG_locked 9
#define LRU_GEN_PGOFF 10
#define LRU_GEN_MASK (7UL << LRU_GEN_PGOFF)
#define LRU_REFS_PGOFF 16
#define LRU_REFS_WIDTH 2
#define LRU_REFS_MASK (3UL << LRU_REFS_PGOFF)
#define LRU_REFS_FLAGS (BIT(PG_workingset))
#define MIN_NR_GENS 2
#define MAX_NR_GENS 4
#define MAX_NR_TIERS 4
#define NR_HIST_GENS 1
#define LRU_GEN_ANON 0
#define LRU_GEN_FILE 1
#define EVICTION_MASK 0xffffUL
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1; } } while (0)
#define VM_WARN_ON_ONCE(x) assert(!(x))
#define VM_WARN_ON_ONCE_PAGE(x,p) assert(!(x))
enum lru_list { LRU_INACTIVE_ANON=0,LRU_ACTIVE_ANON=1,LRU_INACTIVE_FILE=2,LRU_ACTIVE_FILE=3 };
#define LRU_ACTIVE 1
struct list_head { struct list_head *next,*prev; };
static int last_insert;
static void list_init(struct list_head *h) { h->next=h->prev=h; }
static void list_add(struct list_head *e,struct list_head *h) { e->next=h->next;e->prev=h;h->next->prev=e;h->next=e;last_insert=1; }
static void list_add_tail(struct list_head *e,struct list_head *h) { e->next=h;e->prev=h->prev;h->prev->next=e;h->prev=e;last_insert=2; }
static void list_del(struct list_head *e) { e->next->prev=e->prev;e->prev->next=e->next; }
static void list_move(struct list_head *e,struct list_head *h) { list_del(e);list_add(e,h); }
static void list_move_tail(struct list_head *e,struct list_head *h) { list_del(e);list_add_tail(e,h); }
struct mem_cgroup { int id; };
struct pglist_data { int id; };
struct page { unsigned long flags;struct list_head lru;int pages,zone;struct mem_cgroup *memcg;struct pglist_data *pgdat; };
struct lru_gen_struct {
    unsigned long max_seq,min_seq[2],nr_pages[4][2][2];
    unsigned long protected[1][2][3];
    long refaulted[1][2][4];bool enabled;
    struct list_head lists[4][2][2];
};
struct lruvec { struct lru_gen_struct lrugen;long sizes[4]; };
struct scan_control { int reclaim_idx; };
static struct lruvec lv;
static struct mem_cgroup cg={1},other_cg={2};
static struct pglist_data node={1},other_node={2};
static bool skip_hook,in_fault;
static int hook_calls,rcu_depth,restore_calls;
static long stats[6];
enum { WORKINGSET_REFAULT_BASE=0,WORKINGSET_ACTIVATE_BASE=2,WORKINGSET_RESTORE_BASE=4,UNEVICTABLE_PGCULLED=6 };
static int page_is_file_lru(struct page *p) { return !(p->flags&BIT(PG_swapbacked)); }
static int page_zonenum(struct page *p) { return p->zone; }
static int thp_nr_pages(struct page *p) { return p->pages; }
static int order_base_2(unsigned int value) { int n=0;for(unsigned int k=1;k<value;k<<=1)n++;return n; }
#define PAGE_FLAG(name,flag) static bool name(struct page *p) { return !!(p->flags&BIT(flag)); }
PAGE_FLAG(PageActive,PG_active)
PAGE_FLAG(PageUnevictable,PG_unevictable)
PAGE_FLAG(PageSwapCache,PG_swapcache)
PAGE_FLAG(PageDirty,PG_dirty)
PAGE_FLAG(PageWriteback,PG_writeback)
PAGE_FLAG(PageReclaim,PG_reclaim)
PAGE_FLAG(PageAnon,PG_anon)
PAGE_FLAG(PageLocked,PG_locked)
static bool page_evictable(struct page *p) { return !PageUnevictable(p); }
static void SetPageUnevictable(struct page *p) { p->flags|=BIT(PG_unevictable); }
static void SetPageSwapBacked(struct page *p) { p->flags|=BIT(PG_swapbacked); }
static void SetPageWorkingset(struct page *p) { p->flags|=BIT(PG_workingset); }
static unsigned long set_mask_bits(unsigned long *p,unsigned long clear,unsigned long set) { unsigned long old=*p;*p=(*p&~clear)|set;return old; }
static bool try_cmpxchg(unsigned long *p,unsigned long *old,unsigned long value) { if(*p!=*old){*old=*p;return false;}*p=value;return true; }
static void __update_lru_size(struct lruvec *v,enum lru_list lru,int zone,int n) { (void)zone;v->sizes[lru]+=n; }
static void trace_android_vh_lru_gen_add_page_skip(struct lruvec *v,struct page *p,bool *skip) { (void)v;(void)p;hook_calls++;*skip=skip_hook; }
static void trace_android_vh_lru_gen_del_page_skip(struct lruvec *v,struct page *p,bool *skip) { (void)v;(void)p;*skip=false; }
static void add_page_to_lru_list(struct page *p,struct lruvec *v) { (void)p;(void)v;restore_calls++; }
static void add_page_to_lru_list_tail(struct page *p,struct lruvec *v) { (void)p;(void)v;restore_calls++; }
static void __count_vm_events(int item,int n) { (void)item;(void)n; }
/* CMA policy is covered by its separate production-helper suite. */
static bool skip_cma(struct page *p,struct scan_control *sc) { (void)p;(void)sc;return false; }
static struct pglist_data *page_pgdat(struct page *p) { return p->pgdat; }
static struct mem_cgroup *page_memcg_rcu(struct page *p) { return p->memcg; }
static int mem_cgroup_id(struct mem_cgroup *m) { return m->id; }
static struct lruvec *mem_cgroup_lruvec(struct mem_cgroup *m,struct pglist_data *n) { (void)m;(void)n;return &lv; }
static void rcu_read_lock(void) { rcu_depth++; }
static void rcu_read_unlock(void) { assert(rcu_depth>0);rcu_depth--; }
static bool lru_gen_in_fault(void) { return in_fault; }
static void atomic_long_add(int delta,long *count) { *count+=delta; }
static void mod_lruvec_state(struct lruvec *v,int item,int delta) { (void)v;assert(item<6);stats[item]+=delta; }
struct shadow { int memcg_id;struct pglist_data *pgdat;unsigned long token;bool workingset; };
static void unpack_shadow(void *pointer,int *id,struct pglist_data **n,unsigned long *token,bool *ws) {
    struct shadow *s=pointer;*id=s->memcg_id;*n=s->pgdat;*token=s->token;*ws=s->workingset;
}
'''

SUFFIX = r'''
static void init(void) {
    memset(&lv,0,sizeof(lv));memset(stats,0,sizeof(stats));last_insert=0;
    lv.lrugen.max_seq=11;lv.lrugen.min_seq[0]=lv.lrugen.min_seq[1]=8;lv.lrugen.enabled=true;
    for(int g=0;g<4;g++)for(int t=0;t<2;t++)for(int z=0;z<2;z++)list_init(&lv.lrugen.lists[g][t][z]);
    hook_calls=0;skip_hook=in_fault=false;rcu_depth=restore_calls=0;
}
static struct page make_page(unsigned long flags,int pages) {
    struct page p={.flags=flags,.pages=pages,.zone=0,.memcg=&cg,.pgdat=&node};return p;
}
static void insert_oldest(struct page *p) { assert(lru_gen_add_page(&lv,p,true));assert(page_lru_gen(p)==0); }
static struct shadow make_shadow(int refs) {
    struct shadow s={.memcg_id=1,.pgdat=&node,.token=(8UL<<LRU_REFS_WIDTH)|(refs&3),.workingset=refs==4};
    if(refs==4)s.token=(8UL<<LRU_REFS_WIDTH)|3;return s;
}
int main(int argc,char **argv) {
    assert(argc==2);init();int scenario=atoi(argv[1]);
    struct page p=make_page(0,1);struct scan_control sc={.reclaim_idx=0};
    if(scenario==1) {
        CHECK(lru_gen_add_page(&lv,&p,false));CHECK(page_lru_gen(&p)==1 && last_insert==1);
        CHECK(lv.lrugen.nr_pages[1][LRU_GEN_FILE][0]==1 && lv.sizes[LRU_INACTIVE_FILE]==1);
        CHECK(lv.sizes[LRU_ACTIVE_FILE]==0 && !(p.flags&BIT(PG_active)));
    } else if(scenario==2) {
        p.flags=BIT(PG_swapbacked)|BIT(PG_anon);
        CHECK(lru_gen_add_page(&lv,&p,false));CHECK(page_lru_gen(&p)==2 && lv.sizes[LRU_ACTIVE_ANON]==1);
        init();p=make_page(BIT(PG_reclaim)|BIT(PG_dirty),1);
        CHECK(lru_gen_add_page(&lv,&p,false));CHECK(page_lru_gen(&p)==2 && lv.sizes[LRU_ACTIVE_FILE]==1);
    } else if(scenario==3) {
        p.flags=BIT(PG_active);CHECK(lru_gen_add_page(&lv,&p,false));
        CHECK(page_lru_gen(&p)==3 && lv.sizes[LRU_ACTIVE_FILE]==1 && !(p.flags&BIT(PG_active)));
        init();p=make_page(0,1);CHECK(lru_gen_add_page(&lv,&p,true));CHECK(page_lru_gen(&p)==0 && last_insert==2);
        init();lv.lrugen.min_seq[0]=lv.lrugen.min_seq[1]=9;p=make_page(0,1);
        CHECK(lru_gen_add_page(&lv,&p,false));CHECK(page_lru_gen(&p)==1 && lv.sizes[LRU_INACTIVE_FILE]==1);
        init();lv.lrugen.min_seq[0]=lv.lrugen.min_seq[1]=10;p=make_page(0,1);
        CHECK(lru_gen_add_page(&lv,&p,false));CHECK(page_lru_gen(&p)==2 && lv.sizes[LRU_ACTIVE_FILE]==1);
    } else if(scenario==4) {
        p.pages=512;insert_oldest(&p);p.flags|=LRU_REFS_MASK|BIT(PG_workingset);
        CHECK(page_lru_refs(&p)==4 && sort_page(&lv,&p,&sc,3));CHECK(page_lru_gen(&p)==1 && last_insert==2);
        CHECK(lv.lrugen.protected[0][LRU_GEN_FILE][2]==512);
        CHECK(lv.lrugen.nr_pages[0][LRU_GEN_FILE][0]==0 && lv.lrugen.nr_pages[1][LRU_GEN_FILE][0]==512);
        CHECK(lv.sizes[LRU_INACTIVE_FILE]==512 && lv.sizes[LRU_ACTIVE_FILE]==0);
    } else if(scenario==5) {
        insert_oldest(&p);p.flags|=2UL<<LRU_REFS_PGOFF;
        CHECK(!sort_page(&lv,&p,&sc,3));CHECK(page_lru_gen(&p)==0 && !lv.lrugen.protected[0][1][1]);
        p.flags|=BIT(PG_dirty);CHECK(sort_page(&lv,&p,&sc,3));CHECK(page_lru_gen(&p)==1);
    } else if(scenario==6 || scenario==7) {
        struct shadow s=make_shadow(scenario==6?3:4);lru_gen_refault(&p,&s);
        CHECK(page_lru_refs(&p)==4 && stats[WORKINGSET_REFAULT_BASE+1]==1);
        CHECK(stats[WORKINGSET_ACTIVATE_BASE+1]==1 && stats[WORKINGSET_RESTORE_BASE+1]==1 && !rcu_depth);
        CHECK(lv.lrugen.refaulted[0][1][scenario==6?2:3]==1);
    } else if(scenario==8) {
        struct shadow s=make_shadow(2);s.token=(7UL<<LRU_REFS_WIDTH)|2;lru_gen_refault(&p,&s);
        CHECK(!p.flags && stats[WORKINGSET_REFAULT_BASE+1]==1 && !stats[WORKINGSET_ACTIVATE_BASE+1] && !rcu_depth);
        memset(stats,0,sizeof(stats));s=make_shadow(4);p.memcg=&other_cg;lru_gen_refault(&p,&s);
        CHECK(!p.flags && !stats[WORKINGSET_REFAULT_BASE+1] && !rcu_depth);
        p.memcg=&cg;p.pgdat=&other_node;lru_gen_refault(&p,&s);
        CHECK(!p.flags && !stats[WORKINGSET_REFAULT_BASE+1] && !rcu_depth);
    } else if(scenario==9) {
        struct shadow s=make_shadow(0);in_fault=true;lru_gen_refault(&p,&s);
        CHECK(page_lru_refs(&p)==4 && stats[WORKINGSET_RESTORE_BASE+1]==1 && !rcu_depth);
        init();p=make_page(0,1);s=make_shadow(2);lru_gen_refault(&p,&s);
        CHECK(!p.flags && !stats[WORKINGSET_RESTORE_BASE+1] && stats[WORKINGSET_ACTIVATE_BASE+1]==1);
    } else if(scenario==10) {
        skip_hook=true;CHECK(lru_gen_add_page(&lv,&p,false));CHECK(page_lru_gen(&p)==-1 && hook_calls==1);
        CHECK(!lv.sizes[LRU_INACTIVE_FILE] && !lv.sizes[LRU_ACTIVE_FILE]);
        skip_hook=false;lv.lrugen.enabled=false;CHECK(!lru_gen_add_page(&lv,&p,false));CHECK(page_lru_gen(&p)==-1);
        lv.lrugen.enabled=true;p.flags=BIT(PG_unevictable);CHECK(!lru_gen_add_page(&lv,&p,false));
    } else return 2;
    return 0;
}
'''


class MglruCacheProtectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='mglru-cache-')
        inline = (SOURCE_ROOT / 'include/linux/mm_inline.h').read_text()
        vmscan = (SOURCE_ROOT / 'mm/vmscan.c').read_text()
        workingset = (SOURCE_ROOT / 'mm/workingset.c').read_text()
        cls.common = '\n'.join(function(inline, n) for n in (
            'lru_gen_from_seq', 'lru_hist_from_seq', 'lru_tier_from_refs',
            'page_lru_refs', 'page_lru_gen', 'lru_gen_is_active', 'lru_gen_update_size'))
        cls.delete = function(inline, 'lru_gen_del_page')
        cls.promote = function(vmscan, 'page_inc_gen')
        cls.current = {'add': function(inline, 'lru_gen_add_page'),
                       'sort': function(vmscan, 'sort_page'),
                       'refault': function(workingset, 'lru_gen_refault')}
        cls.old = FIXTURE.read_text()
        cls.binary = cls.compile(cls.current, 'fixed')
        old = {'add': function(cls.old, 'lru_gen_add_page'),
               'sort': function(cls.old, 'sort_page'),
               'refault': function(cls.old, 'lru_gen_refault')}
        cls.baseline = cls.compile(old, 'frozen-rc4')

    @classmethod
    def compile(cls, helpers, name):
        path = Path(cls.directory.name) / name
        source = (PREFIX + cls.common + '\n' + helpers['add'] + '\n' + cls.delete + '\n' +
                  cls.promote + '\n' + helpers['sort'] + '\n' + helpers['refault'] + SUFFIX)
        path.with_suffix('.c').write_text(source)
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

    def run_case(self, scenario, binary=None):
        return subprocess.run([str(binary or self.binary), str(scenario)], capture_output=True, text=True)

    def check(self, scenario, old_must_fail=False):
        fixed = self.run_case(scenario)
        self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)
        old = self.run_case(scenario, self.baseline)
        if old_must_fail:
            self.assertNotEqual(old.returncode, 0, 'Frozen rc4 did not expose expected regression')
        else:
            self.assertEqual(old.returncode, 0, old.stdout + old.stderr)

    def test_clean_cache_gets_second_oldest_generation(self):
        self.check(1, old_must_fail=True)

    def test_unready_pages_get_second_youngest_generation(self):
        self.check(2, old_must_fail=True)

    def test_hot_reclaiming_and_short_windows_keep_contracts(self):
        self.check(3)

    def test_saturated_refs_keep_thp_accounting_and_protection(self):
        self.check(4, old_must_fail=True)

    def test_below_threshold_and_dirty_sorting_keep_contracts(self):
        self.check(5)

    def test_three_refs_qualify_for_restore(self):
        self.check(6, old_must_fail=True)

    def test_saturated_refault_restores_full_reference_state(self):
        self.check(7, old_must_fail=True)

    def test_stale_or_different_owner_refaults_keep_filters(self):
        self.check(8)

    def test_fault_path_restores_refs_without_overprotecting_low_refs(self):
        self.check(9, old_must_fail=True)

    def test_vendor_skip_disabled_and_unevictable_keep_contracts(self):
        self.check(10)


if __name__ == '__main__':
    unittest.main()
