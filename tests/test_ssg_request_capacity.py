#!/usr/bin/env python3
"""Exercise compiled SSG metadata helpers, including partial depth updates."""
from pathlib import Path
import unittest
from test_ssg_safety import ROOT, function, run_c
from source_path import SOURCE_ROOT

STUBS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#define unlikely(x) (x)
#define GFP_KERNEL 0
#define min(a, b) ((a) < (b) ? (a) : (b))
struct ssg_request_info { int tgid; unsigned int data_size; };
struct ssg_data {
    struct ssg_request_info *rq_info;
    unsigned int rq_info_count;
    int congestion_threshold_rqs, max_tgroup_rqs;
    unsigned int tgroup_shallow_depth, async_write_shallow_depth;
};
struct elevator_queue { struct ssg_data *elevator_data; };
struct request_queue { unsigned int nr_requests; struct elevator_queue *elevator; };
struct request { int internal_tag; struct request_queue *q; };
struct bitmap { struct { unsigned int depth; } sb; };
struct blk_mq_tags { unsigned int nr_tags; struct bitmap *bitmap_tags; };
struct blk_mq_hw_ctx { struct request_queue *queue; struct blk_mq_tags *sched_tags; };
struct blk_mq_alloc_data { struct request_queue *q; };
struct task { int group_leader; };
static struct task task;
static struct task *current = &task;
static int task_tgid_nr(int leader) { return 17; }
static const int congestion_threshold = 90;
static bool fail_alloc;
static unsigned int allocations;
static void *kcalloc(unsigned int count, size_t size, int flags) {
    allocations++;
    if (fail_alloc) return NULL;
    return calloc(count, size);
}
#define kfree(p) free(p)
static void ssg_set_shallow_depth(struct ssg_data *ssg, struct blk_mq_tags *tags) {}
static void sbitmap_queue_min_shallow_depth(struct bitmap *bitmap, unsigned int depth) {}
static void ssg_blkcg_depth_updated(struct blk_mq_hw_ctx *hctx) {}
'''


class SsgCapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (SOURCE_ROOT / 'block/ssg-iosched.c').read_text()
        cls.code = STUBS + ''.join(function(source, name) for name in (
            'ssg_rq_info', 'ssg_resize_rq_info', 'ssg_depth_updated',
            'ssg_tgroup_shallow_depth'))
        cls.setup = r'''
    struct ssg_data ssg = { .max_tgroup_rqs = 1, .tgroup_shallow_depth = 3 };
    struct elevator_queue elevator = { &ssg };
    struct request_queue q = { .nr_requests = 8, .elevator = &elevator };
    struct bitmap bitmap = { .sb.depth = 6 };
    struct blk_mq_tags tags = { .nr_tags = 8, .bitmap_tags = &bitmap };
    struct blk_mq_hw_ctx hctx = { &q, &tags };
    struct blk_mq_alloc_data data = { &q };
    struct request rq = { .q = &q };
'''

    def run_case(self, body):
        run_c(self.code + 'int main(void) {\n' + self.setup + body + '\n}\n')

    def test_reserved_tags_and_allocated_bounds(self):
        self.run_case(r'''
    ssg_depth_updated(&hctx);
    assert(ssg.rq_info && ssg.rq_info_count == 8);
    rq.internal_tag = 7;  /* Two reserved tags are excluded from bitmap.depth. */
    assert(ssg_rq_info(&ssg, &rq) == &ssg.rq_info[7]);
    rq.internal_tag = -1; assert(!ssg_rq_info(&ssg, &rq));
    rq.internal_tag = 8; assert(!ssg_rq_info(&ssg, &rq));
    assert(!ssg_rq_info(&ssg, NULL));
    q.nr_requests = 64;
    rq.internal_tag = 63; assert(!ssg_rq_info(&ssg, &rq));
    ssg.rq_info[7].tgid = 17;
    assert(ssg_tgroup_shallow_depth(&data) == 3); /* scan capped at 8 */
    q.nr_requests = 4;
    assert(ssg_tgroup_shallow_depth(&data) == 0); /* scan capped at 4 */
    free(ssg.rq_info);
''')

    def test_allocation_failure_preserves_pointer_capacity_and_retries(self):
        self.run_case(r'''
    fail_alloc = true;
    ssg_depth_updated(&hctx);
    assert(!ssg.rq_info && !ssg.rq_info_count);
    assert(ssg_tgroup_shallow_depth(&data) == 0);
    fail_alloc = false;
    ssg_depth_updated(&hctx);
    struct ssg_request_info *old = ssg.rq_info;
    old[7].tgid = 17;
    fail_alloc = true;
    tags.nr_tags = 16; bitmap.sb.depth = 14;
    ssg_depth_updated(&hctx);
    assert(ssg.rq_info == old && ssg.rq_info_count == 8);
    assert(ssg.rq_info[7].tgid == 17);
    rq.internal_tag = 15; assert(!ssg_rq_info(&ssg, &rq));
    q.nr_requests = 16;
    assert(ssg_tgroup_shallow_depth(&data) == 3);
    fail_alloc = false;
    ssg_depth_updated(&hctx);
    assert(ssg.rq_info_count == 16);
    assert(ssg_rq_info(&ssg, &rq) == &ssg.rq_info[15]);
    assert(ssg.rq_info[7].tgid == 0);
    free(ssg.rq_info);
''')

    def test_partial_growth_and_shrink_keep_maximum_safe_capacity(self):
        self.run_case(r'''
    ssg_depth_updated(&hctx);
    /* First hctx grows, while a later hctx fails before q->nr_requests changes. */
    tags.nr_tags = 16; bitmap.sb.depth = 14;
    ssg_depth_updated(&hctx);
    assert(q.nr_requests == 8 && ssg.rq_info_count == 16);
    rq.internal_tag = 15; assert(ssg_rq_info(&ssg, &rq));
    /* A following callback from an unchanged hctx must not shrink storage. */
    tags.nr_tags = 8; bitmap.sb.depth = 6;
    unsigned int calls = allocations;
    ssg_depth_updated(&hctx);
    assert(allocations == calls && ssg.rq_info_count == 16);
    rq.internal_tag = 15; assert(ssg_rq_info(&ssg, &rq));
    /* A successful logical shrink keeps the original nr_tags allocation. */
    q.nr_requests = 4; tags.nr_tags = 16; bitmap.sb.depth = 2;
    ssg_depth_updated(&hctx);
    assert(ssg.rq_info_count == 16);
    ssg.rq_info[15].tgid = 17;
    assert(ssg_tgroup_shallow_depth(&data) == 0);
    free(ssg.rq_info);
''')


if __name__ == '__main__':
    unittest.main()
