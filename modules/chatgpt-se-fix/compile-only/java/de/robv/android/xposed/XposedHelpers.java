package de.robv.android.xposed;

/** Compile-only API descriptors. Never include this class in the APK. */
public final class XposedHelpers {
    private XposedHelpers() {
    }

    public static XC_MethodHook.Unhook findAndHookMethod(
            String className, ClassLoader loader, String methodName, Object... arguments) {
        throw new UnsupportedOperationException("Compile-only Xposed descriptor");
    }

    public static Object getObjectField(Object object, String fieldName) {
        throw new UnsupportedOperationException("Compile-only Xposed descriptor");
    }
}
