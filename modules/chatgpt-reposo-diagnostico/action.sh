#!/system/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
MODDIR=${0%/*}
exec /system/bin/sh "$MODDIR/bin/collect.sh" auto
