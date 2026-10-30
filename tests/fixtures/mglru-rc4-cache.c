/* Production helpers frozen from rc4 before patch 0017.
 * Source revision: 1ebf69612 (current tracked rc4 snapshot).
 * Negative controls only; fixtures do not replace current production helpers.
 */
static inline bool lru_gen_add_page(struct lruvec *lruvec, struct page *page, bool reclaiming)
{
	unsigned long seq;
	unsigned long flags;
	int gen = page_lru_gen(page);
	int type = page_is_file_lru(page);
	int zone = page_zonenum(page);
	struct lru_gen_struct *lrugen = &lruvec->lrugen;
	bool skip = false;

	trace_android_vh_lru_gen_add_page_skip(lruvec, page, &skip);
	if (skip)
		return true;

	VM_WARN_ON_ONCE_PAGE(gen != -1, page);

	if (PageUnevictable(page) || !lrugen->enabled)
		return false;
	/*
	 * There are three common cases for this page:
	 * 1. If it's hot, e.g., freshly faulted in or previously hot and
	 *    migrated, add it to the youngest generation.
	 * 2. If it's cold but can't be evicted immediately, i.e., an anon page
	 *    not in swapcache or a dirty page pending writeback, add it to the
	 *    second oldest generation.
	 * 3. Everything else (clean, cold) is added to the oldest generation.
	 */
	if (PageActive(page))
		seq = lrugen->max_seq;
	else if ((type == LRU_GEN_ANON && !PageSwapCache(page)) ||
		 (PageReclaim(page) &&
		  (PageDirty(page) || PageWriteback(page))))
		seq = lrugen->min_seq[type] + 1;
	else
		seq = lrugen->min_seq[type];

	gen = lru_gen_from_seq(seq);
	flags = (gen + 1UL) << LRU_GEN_PGOFF;
	/* see the comment on MIN_NR_GENS about PG_active */
	set_mask_bits(&page->flags, LRU_GEN_MASK | BIT(PG_active), flags);

	lru_gen_update_size(lruvec, page, -1, gen);
	/* for rotate_reclaimable_page() */
	if (reclaiming)
		list_add_tail(&page->lru, &lrugen->lists[gen][type][zone]);
	else
		list_add(&page->lru, &lrugen->lists[gen][type][zone]);

	return true;
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
	if (tier > tier_idx) {
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

static void lru_gen_refault(struct page *page, void *shadow)
{
	int hist, tier, refs;
	int memcg_id;
	bool workingset;
	unsigned long token;
	unsigned long min_seq;
	struct lruvec *lruvec;
	struct lru_gen_struct *lrugen;
	struct mem_cgroup *memcg;
	struct pglist_data *pgdat;
	int type = page_is_file_lru(page);
	int delta = thp_nr_pages(page);

	unpack_shadow(shadow, &memcg_id, &pgdat, &token, &workingset);

	if (pgdat != page_pgdat(page))
		return;

	rcu_read_lock();

	memcg = page_memcg_rcu(page);
	if (memcg_id != mem_cgroup_id(memcg))
		goto unlock;

	lruvec = mem_cgroup_lruvec(memcg, pgdat);
	lrugen = &lruvec->lrugen;

	mod_lruvec_state(lruvec, WORKINGSET_REFAULT_BASE + type, delta);

	min_seq = READ_ONCE(lrugen->min_seq[type]);
	if ((token >> LRU_REFS_WIDTH) != (min_seq & (EVICTION_MASK >> LRU_REFS_WIDTH)))
		goto unlock;

	hist = lru_hist_from_seq(min_seq);
	/* see the comment in page_lru_refs() */
	refs = (token & (BIT(LRU_REFS_WIDTH) - 1)) + workingset;
	tier = lru_tier_from_refs(refs);

	atomic_long_add(delta, &lrugen->refaulted[hist][type][tier]);
	mod_lruvec_state(lruvec, WORKINGSET_ACTIVATE_BASE + type, delta);

	/*
	 * Count the following two cases as stalls:
	 * 1. For pages accessed through page tables, hotter pages pushed out
	 *    hot pages which refaulted immediately.
	 * 2. For pages accessed multiple times through file descriptors,
	 *    numbers of accesses might have been out of the range.
	 */
	if (lru_gen_in_fault() || refs == BIT(LRU_REFS_WIDTH)) {
		SetPageWorkingset(page);
		mod_lruvec_state(lruvec, WORKINGSET_RESTORE_BASE + type, delta);
	}
unlock:
	rcu_read_unlock();
}
