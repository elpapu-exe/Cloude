package de.robv.android.xposed;

/** Compile-only API descriptor. Never include this class in the APK. */
public final class XposedBridge {
    private XposedBridge() {
    }

    public static synchronized void log(String message) {
        throw new UnsupportedOperationException("Compile-only Xposed descriptor");
    }
}
