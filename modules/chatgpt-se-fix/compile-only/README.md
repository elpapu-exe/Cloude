# Descriptores Xposed: solo para compilar

Este directorio contiene exclusivamente el subconjunto de firmas de la API legacy usado por el módulo. No implementa Xposed ni debe incluirse en `classes.dex`. LSPosed proporciona las clases reales durante la ejecución.

Las firmas y jerarquías se cotejaron con las fuentes públicas de [XposedBridge](https://github.com/rovo89/XposedBridge/tree/art/app/src/main/java/de/robv/android/xposed), incluyendo:

- `IXposedHookLoadPackage`, `IXposedMod` y `callbacks.XC_LoadPackage.LoadPackageParam`.
- `XC_MethodHook`, su constructor público, `beforeHookedMethod(MethodHookParam)` y los campos públicos `thisObject`/`args`.
- `XposedHelpers.findAndHookMethod(String, ClassLoader, String, Object...)`, cuyo retorno es `XC_MethodHook.Unhook`, y `getObjectField(Object, String)`.
- `XposedBridge.log(String)`.

El módulo declara API mínima 82 y usa ese conjunto legacy de métodos. Los stubs representan únicamente los miembros necesarios para enlazarlo; no son una copia completa de la API. Sus métodos funcionales lanzan `UnsupportedOperationException` para evitar que se confundan con una implementación utilizable.

La verificación del APK debe distinguir referencias y definiciones de clase: las referencias a `de.robv.android.xposed` son necesarias, mientras que definir cualquiera de esas clases dentro del APK es un error de empaquetado.
