/* Real production helpers immediately before patch 0018.
 * Includes patch 0017; frozen solely for negative controls.
 * The #else stub is omitted because these tests exercise CONFIG_CMA=y.
 */
static bool skip_cma(struct page *page, struct scan_control *sc)
{
	return !current_is_kswapd() &&
			gfp_migratetype(sc->gfp_mask) != MIGRATE_MOVABLE &&
			get_pageblock_migratetype(page) == MIGRATE_CMA;
}
static unsigned long isolate_lru_pages(unsigned long nr_to_scan,
		struct lruvec *lruvec, struct list_head *dst,
		unsigned long *nr_scanned, struct scan_control *sc,
		enum lru_list lru)
{
	struct list_head *src = &lruvec->lists[lru];
	unsigned long nr_taken = 0;
	unsigned long nr_zone_taken[MAX_NR_ZONES] = { 0 };
	unsigned long nr_skipped[MAX_NR_ZONES] = { 0, };
	unsigned long skipped = 0;
	unsigned long scan, total_scan, nr_pages;
	LIST_HEAD(pages_skipped);

	total_scan = 0;
	scan = 0;
	while (scan < nr_to_scan && !list_empty(src)) {
		struct list_head *move_to = src;
		struct page *page;

		page = lru_to_page(src);
		prefetchw_prev_lru_page(page, src, flags);

		nr_pages = compound_nr(page);
		total_scan += nr_pages;

		if (page_zonenum(page) > sc->reclaim_idx ||
				skip_cma(page, sc)) {
			nr_skipped[page_zonenum(page)] += nr_pages;
			move_to = &pages_skipped;
			goto move;
		}

		/*
		 * Do not count skipped pages because that makes the function
		 * return with no isolated pages if the LRU mostly contains
		 * ineligible pages.  This causes the VM to not reclaim any
		 * pages, triggering a premature OOM.
		 * Account all tail pages of THP.
		 */
		scan += nr_pages;

		if (!PageLRU(page))
			goto move;
		if (!sc->may_unmap && page_mapped(page))
			goto move;

		/*
		 * Be careful not to clear PageLRU until after we're
		 * sure the page is not being freed elsewhere -- the
		 * page release code relies on it.
		 */
		if (unlikely(!get_page_unless_zero(page)))
			goto move;

		if (!TestClearPageLRU(page)) {
			/* Another thread is already isolating this page */
			put_page(page);
			goto move;
		}

		nr_taken += nr_pages;
		nr_zone_taken[page_zonenum(page)] += nr_pages;
		move_to = dst;
move:
		list_move(&page->lru, move_to);
		trace_android_vh_del_page_from_lrulist(page, false, lru);
	}

	/*
	 * Splice any skipped pages to the start of the LRU list. Note that
	 * this disrupts the LRU order when reclaiming for lower zones but
	 * we cannot splice to the tail. If we did then the SWAP_CLUSTER_MAX
	 * scanning would soon rescan the same pages to skip and put the
	 * system at risk of premature OOM.
	 */
	if (!list_empty(&pages_skipped)) {
		int zid;

		list_splice(&pages_skipped, src);
		for (zid = 0; zid < MAX_NR_ZONES; zid++) {
			if (!nr_skipped[zid])
				continue;

			__count_zid_vm_events(PGSCAN_SKIP, zid, nr_skipped[zid]);
			skipped += nr_skipped[zid];
		}
	}
	*nr_scanned = total_scan;
	trace_mm_vmscan_lru_isolate(sc->reclaim_idx, sc->order, nr_to_scan,
				    total_scan, skipped, nr_taken,
				    sc->may_unmap ? 0 : ISOLATE_UNMAPPED, lru);
	update_lru_sizes(lruvec, lru, nr_zone_taken);
	return nr_taken;
}
static bool sort_page(struct lruvec *lruvec, struct page *page, struct scan_control *sc,
		       int tier_idx)
{
	bool success;
	int gen = page_lru_gen(page);
	int type = page_is_file_lru(page);
	int zone = page_zonenum(page);
	int delta = thp_nr_pages(page);
	int refs = page_lru_refs(page);
	int tier = lru_tier_from_refs(refs);
	struct lru_gen_struct *lrugen = &lruvec->lrugen;

	VM_WARN_ON_ONCE_PAGE(gen >= MAX_NR_GENS, page);

	/* unevictable */
	if (!page_evictable(page)) {
		success = lru_gen_del_page(lruvec, page, true);
		VM_WARN_ON_ONCE_PAGE(!success, page);
		SetPageUnevictable(page);
		add_page_to_lru_list(page, lruvec);
		__count_vm_events(UNEVICTABLE_PGCULLED, delta);
		return true;
	}

	/* dirty lazyfree */
	if (type == LRU_GEN_FILE && PageAnon(page) && PageDirty(page)) {
		success = lru_gen_del_page(lruvec, page, true);
		VM_WARN_ON_ONCE_PAGE(!success, page);
		SetPageSwapBacked(page);
		add_page_to_lru_list_tail(page, lruvec);
		return true;
	}

	/* promoted */
	if (gen != lru_gen_from_seq(lrugen->min_seq[type])) {
		list_move(&page->lru, &lrugen->lists[gen][type][zone]);
		return true;
	}

	/* protected */
	if (tier > tier_idx || refs == BIT(LRU_REFS_WIDTH)) {
		int hist = lru_hist_from_seq(lrugen->min_seq[type]);

		gen = page_inc_gen(lruvec, page, false);
		list_move_tail(&page->lru, &lrugen->lists[gen][type][zone]);

		WRITE_ONCE(lrugen->protected[hist][type][tier - 1],
			   lrugen->protected[hist][type][tier - 1] + delta);
		return true;
	}

	/* ineligible */
	if (zone > sc->reclaim_idx || skip_cma(page, sc)) {
		gen = page_inc_gen(lruvec, page, false);
		list_move_tail(&page->lru, &lrugen->lists[gen][type][zone]);
		return true;
	}

	/* waiting for writeback */
	if (PageLocked(page) || PageWriteback(page) ||
	    (type == LRU_GEN_FILE && PageDirty(page))) {
		gen = page_inc_gen(lruvec, page, true);
		list_move(&page->lru, &lrugen->lists[gen][type][zone]);
		return true;
	}

	return false;
}
