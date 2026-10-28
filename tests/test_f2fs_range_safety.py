#!/usr/bin/env python3
"""Compile real F2FS range functions with deterministic writeback/locking stubs.

These check error propagation and effective-range validation, not the filesystem
on a mounted phone. Frozen pre-fix functions must fail both regression cases.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest
from source_path import SOURCE_ROOT


def function(source, name):
    match = re.search(r'^static int ' + re.escape(name) + r'\([^;]*?\)\n\{', source, re.M | re.S)
    if not match:
        raise AssertionError(f'Missing production F2FS function: {name}')
    cursor, depth = match.end(), 1
    while depth:
        depth += (source[cursor] == '{') - (source[cursor] == '}')
        cursor += 1
    return source[match.start():cursor] + '\n'


# Frozen functions from published rc3-rebuild1 before patches 0014 and 0015.
# Their negative controls validate that the harness detects the original defects.
BEFORE_FIX = r'''
static int f2fs_collapse_range(struct inode *inode, loff_t offset, loff_t len)
{
	loff_t new_size;
	int ret;

	if (offset + len >= i_size_read(inode))
		return -EINVAL;

	/* collapse range should be aligned to block size of f2fs. */
	if (offset & (F2FS_BLKSIZE - 1) || len & (F2FS_BLKSIZE - 1))
		return -EINVAL;

	ret = f2fs_convert_inline_inode(inode);
	if (ret)
		return ret;

	/* write out all dirty pages from offset */
	ret = filemap_write_and_wait_range(inode->i_mapping, offset, LLONG_MAX);
	if (ret)
		return ret;

	ret = f2fs_do_collapse(inode, offset, len);
	if (ret)
		return ret;

	/* write out all moved pages, if possible */
	filemap_invalidate_lock(inode->i_mapping);
	filemap_write_and_wait_range(inode->i_mapping, offset, LLONG_MAX);
	truncate_pagecache(inode, offset);

	new_size = i_size_read(inode) - len;
	ret = f2fs_truncate_blocks(inode, new_size, true);
	filemap_invalidate_unlock(inode->i_mapping);
	if (!ret)
		f2fs_i_size_write(inode, new_size);
	return ret;
}

static int f2fs_move_file_range(struct file *file_in, loff_t pos_in,
			struct file *file_out, loff_t pos_out, size_t len)
{
	struct inode *src = file_inode(file_in);
	struct inode *dst = file_inode(file_out);
	struct f2fs_sb_info *sbi = F2FS_I_SB(src);
	size_t olen = len, dst_max_i_size = 0;
	size_t dst_osize;
	int ret;

	if (file_in->f_path.mnt != file_out->f_path.mnt ||
				src->i_sb != dst->i_sb)
		return -EXDEV;

	if (unlikely(f2fs_readonly(src->i_sb)))
		return -EROFS;

	if (!S_ISREG(src->i_mode) || !S_ISREG(dst->i_mode))
		return -EINVAL;

	if (IS_ENCRYPTED(src) || IS_ENCRYPTED(dst))
		return -EOPNOTSUPP;

	if (pos_out < 0 || pos_in < 0)
		return -EINVAL;

	if (src == dst) {
		if (pos_in == pos_out)
			return 0;
		if (pos_out > pos_in && pos_out < pos_in + len)
			return -EINVAL;
	}

	inode_lock(src);
	if (src != dst) {
		ret = -EBUSY;
		if (!inode_trylock(dst))
			goto out;
	}

	if (f2fs_compressed_file(src) || f2fs_compressed_file(dst) ||
		f2fs_is_pinned_file(src) || f2fs_is_pinned_file(dst)) {
		ret = -EOPNOTSUPP;
		goto out_unlock;
	}

	ret = -EINVAL;
	if (pos_in + len > src->i_size || pos_in + len < pos_in)
		goto out_unlock;
	if (len == 0)
		olen = len = src->i_size - pos_in;
	if (pos_in + len == src->i_size)
		len = ALIGN(src->i_size, F2FS_BLKSIZE) - pos_in;
	if (len == 0) {
		ret = 0;
		goto out_unlock;
	}

	dst_osize = dst->i_size;
	if (pos_out + olen > dst->i_size)
		dst_max_i_size = pos_out + olen;

	/* verify the end result is block aligned */
	if (!IS_ALIGNED(pos_in, F2FS_BLKSIZE) ||
			!IS_ALIGNED(pos_in + len, F2FS_BLKSIZE) ||
			!IS_ALIGNED(pos_out, F2FS_BLKSIZE))
		goto out_unlock;

	ret = f2fs_convert_inline_inode(src);
	if (ret)
		goto out_unlock;

	ret = f2fs_convert_inline_inode(dst);
	if (ret)
		goto out_unlock;

	/* write out all dirty pages from offset */
	ret = filemap_write_and_wait_range(src->i_mapping,
					pos_in, pos_in + len);
	if (ret)
		goto out_unlock;

	ret = filemap_write_and_wait_range(dst->i_mapping,
					pos_out, pos_out + len);
	if (ret)
		goto out_unlock;

	f2fs_balance_fs(sbi, true);

	f2fs_down_write(&F2FS_I(src)->i_gc_rwsem[WRITE]);
	if (src != dst) {
		ret = -EBUSY;
		if (!f2fs_down_write_trylock(&F2FS_I(dst)->i_gc_rwsem[WRITE]))
			goto out_src;
	}

	f2fs_lock_op(sbi);
	ret = __exchange_data_block(src, dst, pos_in >> F2FS_BLKSIZE_BITS,
				pos_out >> F2FS_BLKSIZE_BITS,
				len >> F2FS_BLKSIZE_BITS, false);

	if (!ret) {
		if (dst_max_i_size)
			f2fs_i_size_write(dst, dst_max_i_size);
		else if (dst_osize != dst->i_size)
			f2fs_i_size_write(dst, dst_osize);
	}
	f2fs_unlock_op(sbi);

	if (src != dst)
		f2fs_up_write(&F2FS_I(dst)->i_gc_rwsem[WRITE]);
out_src:
	f2fs_up_write(&F2FS_I(src)->i_gc_rwsem[WRITE]);
out_unlock:
	if (src != dst)
		inode_unlock(dst);
out:
	inode_unlock(src);
	return ret;
}
'''

PREFIX = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#define F2FS_BLKSIZE 4096
#define F2FS_BLKSIZE_BITS 12
#define WRITE 1
#define unlikely(x) (x)
#define IS_ALIGNED(value, alignment) (((value) & ((alignment) - 1)) == 0)
#define ALIGN(value, alignment) (((value) + (loff_t)(alignment) - 1) & ~((loff_t)(alignment) - 1))
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "CHECK failed at %d: %s\n", __LINE__, #x); return 1; } } while (0)
struct address_space { int invalidate_locked; };
struct f2fs_sb_info { int op_locked; };
struct f2fs_inode_info { int i_gc_rwsem[2]; };
struct inode {
    loff_t i_size;
    unsigned int i_mode;
    struct f2fs_sb_info *i_sb;
    struct address_space *i_mapping;
    struct f2fs_inode_info info;
    int inode_locked;
    bool encrypted, compressed, pinned;
};
struct file { struct inode *inode; struct { void *mnt; } f_path; };
#define F2FS_I(inode) (&(inode)->info)
#define F2FS_I_SB(inode) ((inode)->i_sb)
#define IS_ENCRYPTED(inode) ((inode)->encrypted)
static int wb_calls, wb_results[2], convert_calls, convert_error;
static int collapse_calls, collapse_error, cache_truncations, block_truncations;
static int truncate_error, size_writes, exchange_calls;
static loff_t truncated_size;
static size_t exchanged_blocks;
static bool readonly;
static loff_t i_size_read(struct inode *inode) { return inode->i_size; }
static int f2fs_convert_inline_inode(struct inode *inode)
{ (void)inode; convert_calls++; return convert_error; }
static int filemap_write_and_wait_range(struct address_space *mapping, loff_t start, loff_t end)
{ (void)mapping; assert(start >= 0 && end >= start); assert(wb_calls < 2); return wb_results[wb_calls++]; }
static int f2fs_do_collapse(struct inode *inode, loff_t offset, loff_t len)
{ (void)inode; (void)offset; (void)len; collapse_calls++; return collapse_error; }
static void filemap_invalidate_lock(struct address_space *mapping)
{ assert(!mapping->invalidate_locked); mapping->invalidate_locked = 1; }
static void filemap_invalidate_unlock(struct address_space *mapping)
{ assert(mapping->invalidate_locked); mapping->invalidate_locked = 0; }
static void truncate_pagecache(struct inode *inode, loff_t offset)
{ assert(inode->i_mapping->invalidate_locked); (void)offset; cache_truncations++; }
static int f2fs_truncate_blocks(struct inode *inode, loff_t size, bool lock)
{ assert(inode->i_mapping->invalidate_locked && lock); block_truncations++; truncated_size = size; return truncate_error; }
static void f2fs_i_size_write(struct inode *inode, loff_t size)
{ size_writes++; inode->i_size = size; }
static struct inode *file_inode(struct file *file) { return file->inode; }
static bool f2fs_readonly(struct f2fs_sb_info *sbi) { (void)sbi; return readonly; }
static bool f2fs_compressed_file(struct inode *inode) { return inode->compressed; }
static bool f2fs_is_pinned_file(struct inode *inode) { return inode->pinned; }
static void inode_lock(struct inode *inode)
{ assert(!inode->inode_locked); inode->inode_locked = 1; }
static bool inode_trylock(struct inode *inode)
{ inode_lock(inode); return true; }
static void inode_unlock(struct inode *inode)
{ assert(inode->inode_locked); inode->inode_locked = 0; }
static void f2fs_balance_fs(struct f2fs_sb_info *sbi, bool need)
{ (void)sbi; assert(need); }
static void f2fs_down_write(int *lock) { assert(!*lock); *lock = 1; }
static bool f2fs_down_write_trylock(int *lock) { f2fs_down_write(lock); return true; }
static void f2fs_up_write(int *lock) { assert(*lock); *lock = 0; }
static void f2fs_lock_op(struct f2fs_sb_info *sbi)
{ assert(!sbi->op_locked); sbi->op_locked = 1; }
static void f2fs_unlock_op(struct f2fs_sb_info *sbi)
{ assert(sbi->op_locked); sbi->op_locked = 0; }
static int __exchange_data_block(struct inode *src, struct inode *dst,
    size_t start_in, size_t start_out, size_t blocks, bool full)
{
    assert(src->inode_locked && dst->inode_locked);
    assert(src->info.i_gc_rwsem[WRITE] && dst->info.i_gc_rwsem[WRITE]);
    assert(src->i_sb->op_locked && !full);
    (void)start_in; (void)start_out;
    exchange_calls++; exchanged_blocks = blocks; return 0;
}
'''

HARNESS = r'''
static bool locks_released(struct inode *src, struct inode *dst)
{
    return !src->inode_locked && !dst->inode_locked &&
        !src->info.i_gc_rwsem[WRITE] && !dst->info.i_gc_rwsem[WRITE] &&
        !src->i_mapping->invalidate_locked && !dst->i_mapping->invalidate_locked &&
        !src->i_sb->op_locked;
}
int main(int argc, char **argv)
{
    assert(argc == 2);
    struct f2fs_sb_info sbi = {0};
    struct address_space src_mapping = {0}, dst_mapping = {0};
    struct inode src = { .i_size = 4 * F2FS_BLKSIZE, .i_mode = S_IFREG,
        .i_sb = &sbi, .i_mapping = &src_mapping };
    struct inode dst = { .i_size = 4 * F2FS_BLKSIZE, .i_mode = S_IFREG,
        .i_sb = &sbi, .i_mapping = &dst_mapping };
    struct file input = { .inode = &src, .f_path = { &sbi } };
    struct file output = { .inode = &dst, .f_path = { &sbi } };
    switch (atoi(argv[1])) {
    case 0: /* First writeback failure never starts collapse or takes invalidate lock. */
        wb_results[0] = -EIO;
        CHECK(f2fs_collapse_range(&src, F2FS_BLKSIZE, F2FS_BLKSIZE) == -EIO);
        CHECK(wb_calls == 1 && !collapse_calls);
        CHECK(!cache_truncations && !block_truncations && !size_writes);
        CHECK(src.i_size == 4 * F2FS_BLKSIZE && locks_released(&src, &dst));
        break;
    case 1: /* Moved-page writeback failure must not truncate or claim success. */
        wb_results[1] = -EIO;
        CHECK(f2fs_collapse_range(&src, F2FS_BLKSIZE, F2FS_BLKSIZE) == -EIO);
        CHECK(wb_calls == 2 && collapse_calls == 1);
        CHECK(!cache_truncations && !block_truncations && !size_writes);
        CHECK(src.i_size == 4 * F2FS_BLKSIZE && locks_released(&src, &dst));
        break;
    case 2: /* Successful collapse preserves the normal shrink and unlocks. */
        CHECK(f2fs_collapse_range(&src, F2FS_BLKSIZE, F2FS_BLKSIZE) == 0);
        CHECK(wb_calls == 2 && collapse_calls == 1);
        CHECK(cache_truncations == 1 && block_truncations == 1 && size_writes == 1);
        CHECK(truncated_size == 3 * F2FS_BLKSIZE && src.i_size == truncated_size);
        CHECK(locks_released(&src, &dst));
        break;
    case 3: /* Effective zero length expands to EOF before same-inode overlap check. */
        CHECK(f2fs_move_file_range(&input, 0, &input, F2FS_BLKSIZE, 0) == -EINVAL);
        CHECK(!exchange_calls && !wb_calls && !size_writes && !convert_calls);
        CHECK(src.i_size == 4 * F2FS_BLKSIZE && locks_released(&src, &dst));
        break;
    case 4: /* Explicit overlapping, small, equal, empty and non-overlapping ranges. */
        CHECK(f2fs_move_file_range(&input, 0, &input, F2FS_BLKSIZE, 2 * F2FS_BLKSIZE) == -EINVAL);
        CHECK(!exchange_calls && !wb_calls && locks_released(&src, &dst));
        CHECK(f2fs_move_file_range(&input, 0, &input, F2FS_BLKSIZE, 1) == -EINVAL);
        CHECK(!exchange_calls && !wb_calls && locks_released(&src, &dst));
        CHECK(f2fs_move_file_range(&input, F2FS_BLKSIZE, &input, F2FS_BLKSIZE, 0) == 0);
        CHECK(f2fs_move_file_range(&input, src.i_size, &input, 0, 0) == 0);
        CHECK(!exchange_calls && !wb_calls && locks_released(&src, &dst));
        CHECK(f2fs_move_file_range(&input, 0, &input, 2 * F2FS_BLKSIZE, F2FS_BLKSIZE) == 0);
        CHECK(exchange_calls == 1 && exchanged_blocks == 1 && wb_calls == 2);
        CHECK(src.i_size == 4 * F2FS_BLKSIZE && locks_released(&src, &dst));
        break;
    case 5: /* Separate inodes may have overlapping numerical offsets and len zero. */
        CHECK(f2fs_move_file_range(&input, 0, &output, F2FS_BLKSIZE, 0) == 0);
        CHECK(exchange_calls == 1 && exchanged_blocks == 4 && wb_calls == 2);
        CHECK(size_writes == 1 && dst.i_size == 5 * F2FS_BLKSIZE);
        CHECK(src.i_size == 4 * F2FS_BLKSIZE && locks_released(&src, &dst));
        break;
    default:
        return 2;
    }
    return 0;
}
'''


class F2fsRangeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='f2fs-range-tests-')
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        production = (SOURCE_ROOT / 'fs/f2fs/file.c').read_text()
        cls.executables = {}
        for label, source in (('current', production), ('before', BEFORE_FIX)):
            code = PREFIX + ''.join(function(source, name) for name in (
                'f2fs_collapse_range', 'f2fs_move_file_range')) + HARNESS
            path, executable = root / (label + '.c'), root / label
            path.write_text(code)
            result = subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-O1', '-g',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                str(path), '-o', str(executable)], capture_output=True, text=True)
            if result.returncode:
                raise AssertionError(result.stderr)
            cls.executables[label] = executable

    def run_case(self, number, *, negative_control=False):
        result = subprocess.run([str(self.executables['current']), str(number)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        if negative_control:
            old = subprocess.run([str(self.executables['before']), str(number)],
                                 capture_output=True, text=True, timeout=10)
            self.assertNotEqual(old.returncode, 0, 'Pre-fix source unexpectedly passed the regression')
            self.assertIn('CHECK failed', old.stderr)

    def test_collapse_initial_writeback_failure(self):
        self.run_case(0)

    def test_collapse_moved_page_writeback_failure(self):
        self.run_case(1, negative_control=True)

    def test_collapse_success(self):
        self.run_case(2)

    def test_move_zero_length_same_inode_overlap(self):
        self.run_case(3, negative_control=True)

    def test_move_explicit_small_empty_equal_and_nonoverlap_ranges(self):
        self.run_case(4)

    def test_move_separate_inodes(self):
        self.run_case(5)


if __name__ == '__main__':
    unittest.main()
