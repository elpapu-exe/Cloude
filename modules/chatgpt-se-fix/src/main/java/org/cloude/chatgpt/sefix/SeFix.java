package org.cloude.chatgpt.sefix;

import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

/** Experimental workaround for the absent eSE1 HAL on the tested tapas Android 13 ROM. */
public final class SeFix implements IXposedHookLoadPackage {
    private static final String PACKAGE = "com.android.se";
    private static final String ESE_FEATURE = "android.hardware.se.omapi.ese";
    private static final String UICC_FEATURE = "android.hardware.se.omapi.uicc";
    private static final String PREFIX = "ChatGPT SE Fix: ";

    @Override
    public void handleLoadPackage(XC_LoadPackage.LoadPackageParam loaded) {
        if (loaded == null || !PACKAGE.equals(loaded.packageName)
                || !PACKAGE.equals(loaded.processName)) {
            return;
        }

        try {
            if (Build.VERSION.SDK_INT != 33 || !"tapas".equals(Build.DEVICE)) {
                logSafely("inactive: this build only supports tapas on Android 13.");
                return;
            }

            XposedHelpers.findAndHookMethod(
                    "com.android.se.Terminal", loaded.classLoader, "initialize", boolean.class,
                    new XC_MethodHook() {
                        @Override
                        protected void beforeHookedMethod(MethodHookParam call) {
                            keepSimAndAvailableHardwareIntact(call);
                        }
                    });
            logSafely("installed the guarded Terminal.initialize hook.");
        } catch (Throwable failure) {
            logSafely("hook unavailable; original behavior retained ("
                    + failure.getClass().getSimpleName() + ").");
        }
    }

    private static void keepSimAndAvailableHardwareIntact(XC_MethodHook.MethodHookParam call) {
        try {
            if (call == null || call.args == null || call.args.length != 1
                    || !Boolean.TRUE.equals(call.args[0])) {
                return;
            }

            Object name = XposedHelpers.getObjectField(call.thisObject, "mName");
            if (!"eSE1".equals(name)) {
                return;
            }

            Object storedContext = XposedHelpers.getObjectField(call.thisObject, "mContext");
            if (!(storedContext instanceof Context)) {
                logSafely("eSE1 context unavailable; original retry retained.");
                return;
            }
            PackageManager packages = ((Context) storedContext).getPackageManager();
            if (packages == null) {
                logSafely("feature information unavailable; original retry retained.");
                return;
            }

            // The tested ROM declares UICC but no embedded SecureElement. Never alter SIM retries.
            if (packages.hasSystemFeature(ESE_FEATURE)
                    || !packages.hasSystemFeature(UICC_FEATURE)) {
                return;
            }

            // This is the only mutation: original HAL lookup still runs, without waiting for eSE1.
            call.args[0] = Boolean.FALSE;
            logSafely("eSE1 lookup will not wait; SIM initialization is unchanged.");
        } catch (Throwable failure) {
            // All fallible checks precede the argument assignment; do not replace a result/exception.
            logSafely("guard check failed; original retry retained ("
                    + failure.getClass().getSimpleName() + ").");
        }
    }

    private static void logSafely(String message) {
        try {
            XposedBridge.log(PREFIX + message);
        } catch (Throwable ignored) {
            // A logging failure must never interrupt SecureElement initialization.
        }
    }
}
