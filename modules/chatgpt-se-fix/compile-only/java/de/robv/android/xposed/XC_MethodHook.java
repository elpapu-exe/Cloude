package de.robv.android.xposed;

import de.robv.android.xposed.callbacks.XCallback;

/** Compile-only API descriptors. Every implementation comes from LSPosed at runtime. */
public abstract class XC_MethodHook extends XCallback {
    public XC_MethodHook() {
        throw new UnsupportedOperationException("Compile-only Xposed descriptor");
    }

    protected void beforeHookedMethod(MethodHookParam param) throws Throwable {
        throw new UnsupportedOperationException("Compile-only Xposed descriptor");
    }

    public static final class MethodHookParam extends XCallback.Param {
        public Object thisObject;
        public Object[] args;
    }

    public class Unhook {
    }
}
