// SPDX-License-Identifier: GPL-2.0
/*
 * KernelSpace Profiles
 *
 * This Linux kernel module provides a framework for managing and switching between system profiles or modes
 * at the kernel level. Each profile represents a specific configuration of kernel features and settings
 * optimized for different use cases such as battery life, balanced performance, or maximum performance.
 *
 * The module supports various subsystems, including MSM DRM, MI DRM, and framebuffer (FB). It integrates
 * with these subsystems to receive notifications about screen state changes and adjust the active profile
 * accordingly.
 *
 * The module offers functions for setting the profile mode, overriding the mode temporarily, and retrieving
 * the active profile mode. Profiles can be dynamically switched based on system events, user requests, or
 * time-based rules.
 *
 * For more information and usage examples, refer to the README file at:
 * https://github.com/dakkshesh07/Kprofiles/blob/main/README.md
 *
 * Copyright (C) 2021-2023 Dakkshesh <dakkshesh5@gmail.com>
 * Version: 6.0.0
 * License: GPL-2.0
 */

#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/delay.h>
#include <linux/module.h>
#include <linux/moduleparam.h>
#ifdef CONFIG_AUTO_KPROFILES_MSM_DRM
#include <linux/msm_drm_notify.h>
#elif defined(CONFIG_AUTO_KPROFILES_MI_DRM)
#include <drm/drm_notifier_mi.h>
#elif defined(CONFIG_AUTO_KPROFILES_FB)
#include <linux/fb.h>
#endif
#include "version.h"
#include <linux/notifier.h>
#include <linux/kthread.h>
#include <linux/cpufreq.h>
#include <linux/workqueue.h>

#ifdef CONFIG_AUTO_KPROFILES_MSM_DRM
#define KP_EVENT_BLANK MSM_DRM_EVENT_BLANK
#define KP_BLANK_POWERDOWN MSM_DRM_BLANK_POWERDOWN
#define KP_BLANK_UNBLANK MSM_DRM_BLANK_UNBLANK
#define kp_events msm_drm_notifier
#elif defined(CONFIG_AUTO_KPROFILES_MI_DRM)
#define KP_EVENT_BLANK MI_DRM_EVENT_BLANK
#define KP_BLANK_POWERDOWN MI_DRM_BLANK_POWERDOWN
#define KP_BLANK_UNBLANK MI_DRM_BLANK_UNBLANK
#define kp_events mi_drm_notifier
#elif defined(CONFIG_AUTO_KPROFILES_FB)
#define KP_EVENT_BLANK FB_EVENT_BLANK
#define KP_BLANK_POWERDOWN FB_BLANK_POWERDOWN
#define KP_BLANK_UNBLANK FB_BLANK_UNBLANK
#define kp_events fb_event
#endif

static BLOCKING_NOTIFIER_HEAD(kp_mode_notifier);
unsigned int KP_MODE_CHANGE = 0x80000000;
EXPORT_SYMBOL(KP_MODE_CHANGE);

static unsigned int kp_override_mode;
static bool kp_override;
#ifdef CONFIG_AUTO_KPROFILES
static bool screen_on = true;
#endif

static bool auto_kp __read_mostly = !IS_ENABLED(CONFIG_AUTO_KPROFILES_NONE);
module_param(auto_kp, bool, 0664);
MODULE_PARM_DESC(auto_kp, "Enable/disable automatic kernel profile management");

static unsigned int kp_mode = CONFIG_KP_DEFAULT_MODE;

static struct kobject *kp_kobj;

DEFINE_MUTEX(kp_set_mode_rb_lock);
DEFINE_SPINLOCK(kp_set_mode_lock);

#ifdef CONFIG_KP_VERBOSE_DEBUG
#define kp_dbg(fmt, ...) pr_info(fmt, ##__VA_ARGS__)
#else
#define kp_dbg(fmt, ...)
#endif

#define kp_err(fmt, ...) pr_err(fmt, ##__VA_ARGS__)
#define kp_info(fmt, ...) pr_info(fmt, ##__VA_ARGS__)

static void kp_trigger_mode_change_event(void);
static void kp_mode_change_workfn(struct work_struct *work);
static DECLARE_WORK(kp_mode_change_work, kp_mode_change_workfn);

/**
 * kp_set_mode_rollback - Change profile to a given mode for a specific duration
 * @level: The profile mode level to set (0-3)
 * @duration_ms: The duration to keep the profile mode in milliseconds
 *
 * This function changes the profile to the specified mode for a specific
 * duration during any in-kernel event, and then returns to the previously
 * active mode.
 * The caller must be in sleepable context. Notifications are deferred and
 * rapid transitions may coalesce.
 *
 * Usage example: kp_set_mode_rollback(3, 55);
 */
void kp_set_mode_rollback(unsigned int level, unsigned int duration_ms)
{
	unsigned long flags;

	if (unlikely(level > 3)) {
		kp_err("Invalid mode requested, skipping mode change.\n");
		return;
	}

#ifdef CONFIG_AUTO_KPROFILES
	if (!READ_ONCE(screen_on)) {
		kp_dbg("Screen is off, skipping mode change.\n");
		return;
	}
#endif

	if (!READ_ONCE(auto_kp)) {
		kp_dbg("Auto Kprofiles is disabled, skipping mode change.\n");
		return;
	}

	mutex_lock(&kp_set_mode_rb_lock);
	spin_lock_irqsave(&kp_set_mode_lock, flags);
	kp_override_mode = level;
	kp_override = true;
	spin_unlock_irqrestore(&kp_set_mode_lock, flags);
	kp_trigger_mode_change_event();
	msleep(duration_ms);
	spin_lock_irqsave(&kp_set_mode_lock, flags);
	kp_override = false;
	spin_unlock_irqrestore(&kp_set_mode_lock, flags);
	kp_trigger_mode_change_event();
	mutex_unlock(&kp_set_mode_rb_lock);
}
EXPORT_SYMBOL(kp_set_mode_rollback);

static __always_inline int __kp_set_mode(unsigned int level)
{
	if (unlikely(level > 3))
		return -EINVAL;

	WRITE_ONCE(kp_mode, level);
	return 0;
}

/**
 * kp_set_mode - Change profile to a given mode
 * @level: The profile mode level to set (0-3)
 *
 * This function changes the profile to the specified mode during any
 * in-kernel event.
 * State changes are immediate; blocking notifications are deferred so that
 * this function can also be called from atomic context.
 *
 * Usage example: kp_set_mode(3);
 */
void kp_set_mode(unsigned int level)
{
	unsigned long flags;

	if (unlikely(level > 3)) {
		kp_err("Invalid mode requested, skipping mode change.\n");
		return;
	}

#ifdef CONFIG_AUTO_KPROFILES
	if (!READ_ONCE(screen_on)) {
		kp_dbg("Screen is off, skipping mode change.\n");
		return;
	}
#endif

	if (!READ_ONCE(auto_kp)) {
		kp_dbg("Auto Kprofiles is disabled, skipping mode change.\n");
		return;
	}

	spin_lock_irqsave(&kp_set_mode_lock, flags);
	__kp_set_mode(level);
	spin_unlock_irqrestore(&kp_set_mode_lock, flags);
	kp_trigger_mode_change_event();
}
EXPORT_SYMBOL(kp_set_mode);

/**
 * kp_active_mode - Get the currently active profile mode
 *
 * This function returns a number from 0 to 3 depending on the active profile mode.
 * The returned value can be used in conditions to disable/enable or tune kernel
 * features according to the profile mode.
 *
 * Return:
 * The currently active profile mode (0-3)
 *
 * Usage example:
 *
 * switch (kp_active_mode()) {
 * case 1:
 *     // Things to be done when battery profile is active
 *     break;
 * case 2:
 *     // Things to be done when balanced profile is active
 *     break;
 * case 3:
 *     // Things to be done when performance profile is active
 *     break;
 * default:
 *     // Things to be done when kprofiles is disabled
 *     break;
 * }
 */
int kp_active_mode(void)
{
	unsigned long flags;
	unsigned int mode;
	bool invalid = false;

	spin_lock_irqsave(&kp_set_mode_lock, flags);
#ifdef CONFIG_AUTO_KPROFILES
	if (!screen_on && READ_ONCE(auto_kp)) {
		mode = 1;
		goto unlock;
	}
#endif

	if (kp_override) {
		mode = kp_override_mode;
		goto unlock;
	}

	if (unlikely(kp_mode > 3)) {
		WRITE_ONCE(kp_mode, 0);
		invalid = true;
	}
	mode = kp_mode;
unlock:
	spin_unlock_irqrestore(&kp_set_mode_lock, flags);
	if (invalid) {
		kp_trigger_mode_change_event();
		kp_err("Invalid value passed, falling back to level 0\n");
	}

	return mode;
}
EXPORT_SYMBOL(kp_active_mode);

/**
 * kp_trigger_mode_change_event - Trigger a mode change event
 *
 * Queue notification of the latest active mode. This is safe for atomic
 * callers: blocking listeners run in process context, outside the state lock.
 * Rapid transitions may coalesce; the event describes the mode sampled by the
 * worker, rather than promising delivery of every intermediate transition.
 */
static __always_inline void kp_trigger_mode_change_event(void)
{
	schedule_work(&kp_mode_change_work);
}

static void kp_mode_change_workfn(struct work_struct *work)
{
	unsigned int current_mode = kp_active_mode();

	blocking_notifier_call_chain(&kp_mode_notifier, KP_MODE_CHANGE,
				     (void *)(uintptr_t)current_mode);
}

/**
 * kp_notifier_register_client - Register a notifier client for profile mode changes
 * @nb: The notifier block to register
 *
 * This function registers a notifier client to receive notifications about profile mode changes.
 *
 * Return:
 * 0 on success, or an error code on failure.
 */
int kp_notifier_register_client(struct notifier_block *nb)
{
	return blocking_notifier_chain_register(&kp_mode_notifier, nb);
}
EXPORT_SYMBOL(kp_notifier_register_client);

/**
 * kp_notifier_unregister_client - Unregister a notifier client for profile mode changes
 * @nb: The notifier block to unregister
 *
 * This function unregisters a previously registered notifier client for profile mode changes.
 *
 * Return:
 * 0 on success, or an error code on failure.
 */
int kp_notifier_unregister_client(struct notifier_block *nb)
{
	return blocking_notifier_chain_unregister(&kp_mode_notifier, nb);
}
EXPORT_SYMBOL(kp_notifier_unregister_client);

#ifdef CONFIG_AUTO_KPROFILES
static inline int kp_display_notifier_callback(struct notifier_block *self,
					       unsigned long event, void *data)
{
	struct kp_events *evdata = data;
	unsigned int blank;
	unsigned long flags;
	bool changed = false;

	if (event != KP_EVENT_BLANK)
		return 0;

	if (evdata && evdata->data) {
		blank = *(int *)(evdata->data);
		spin_lock_irqsave(&kp_set_mode_lock, flags);
		switch (blank) {
		case KP_BLANK_POWERDOWN:
			if (!screen_on)
				break;
			WRITE_ONCE(screen_on, false);
			changed = true;
			break;
		case KP_BLANK_UNBLANK:
			if (screen_on)
				break;
			WRITE_ONCE(screen_on, true);
			changed = true;
			break;
		default:
			break;
		}
		spin_unlock_irqrestore(&kp_set_mode_lock, flags);
		if (changed)
			kp_trigger_mode_change_event();
	}

	return NOTIFY_OK;
}

static struct notifier_block kp_display_notifier_block = {
	.notifier_call = kp_display_notifier_callback,
};

static inline int kp_register_display_notifier(void)
{
	int ret = 0;

#ifdef CONFIG_AUTO_KPROFILES_MSM_DRM
	ret = msm_drm_register_client(&kp_display_notifier_block);
#elif defined(CONFIG_AUTO_KPROFILES_MI_DRM)
	ret = mi_drm_register_client(&kp_display_notifier_block);
#elif defined(CONFIG_AUTO_KPROFILES_FB)
	ret = fb_register_client(&kp_display_notifier_block);
#endif

	return ret;
}

static inline void kp_unregister_display_notifier(void)
{
#ifdef CONFIG_AUTO_KPROFILES_MSM_DRM
	msm_drm_unregister_client(&kp_display_notifier_block);
#elif defined(CONFIG_AUTO_KPROFILES_MI_DRM)
	mi_drm_unregister_client(&kp_display_notifier_block);
#elif defined(CONFIG_AUTO_KPROFILES_FB)
	fb_unregister_client(&kp_display_notifier_block);
#endif
}

#else
static inline int kp_register_display_notifier(void)
{
	return 0;
}
static inline void kp_unregister_display_notifier(void)
{
}
#endif

static inline ssize_t kp_mode_show(struct kobject *kobj,
				   struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "%u\n", READ_ONCE(kp_mode));
}

static inline ssize_t kp_mode_store(struct kobject *kobj,
				    struct kobj_attribute *attr,
				    const char *buf, size_t count)
{
	unsigned int new_mode;
	unsigned long flags;
	int ret;

	ret = kstrtouint(buf, 10, &new_mode);
	if (ret)
		return ret;

	if (unlikely(new_mode > 3)) {
		kp_err("User changed mode is invalid, skipping mode change.\n");
		return -EINVAL;
	}
	spin_lock_irqsave(&kp_set_mode_lock, flags);
	__kp_set_mode(new_mode);
	spin_unlock_irqrestore(&kp_set_mode_lock, flags);

	return count;
}

static struct kobj_attribute kp_mode_attribute =
	__ATTR(kp_mode, 0664, kp_mode_show, kp_mode_store);

static struct attribute *kp_attrs[] = {
	&kp_mode_attribute.attr,
	NULL,
};

static struct attribute_group kp_attr_group = {
	.attrs = kp_attrs,
};

static int __init kp_init(void)
{
	int ret = 0;

	kp_kobj = kobject_create_and_add("kprofiles", kernel_kobj);
	if (!kp_kobj) {
		kp_err("Failed to create Kprofiles kobject\n");
		ret = -ENOMEM;
		goto cancel_work;
	}

	ret = sysfs_create_group(kp_kobj, &kp_attr_group);
	if (ret) {
		kp_err("Failed to create sysfs attributes for Kprofiles\n");
		goto put_kobject;
	}

	ret = kp_register_display_notifier();
	if (ret) {
		kp_err("Failed to register Kprofiles display notifier, err: %d\n",
		       ret);
		goto remove_sysfs;
	}

	kp_info("Kprofiles " KPROFILES_VERSION
		" loaded successfully. For further details, visit https://github.com/dakkshesh07/Kprofiles/blob/main/README.md\n");
	kp_info("Copyright (C) 2021-2023 Dakkshesh <dakkshesh5@gmail.com>.\n");

	return ret;

remove_sysfs:
	sysfs_remove_group(kp_kobj, &kp_attr_group);
put_kobject:
	kobject_put(kp_kobj);
cancel_work:
	cancel_work_sync(&kp_mode_change_work);
	return ret;
}
module_init(kp_init);

static void __exit kp_exit(void)
{
	kp_unregister_display_notifier();
	sysfs_remove_group(kp_kobj, &kp_attr_group);
	cancel_work_sync(&kp_mode_change_work);
	kobject_put(kp_kobj);
}
module_exit(kp_exit);

MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("KernelSpace Profiles");
MODULE_AUTHOR("Dakkshesh <dakkshesh5@gmail.com>");
MODULE_VERSION(KPROFILES_VERSION);
