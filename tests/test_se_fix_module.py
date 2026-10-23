#!/usr/bin/env python3
"""Execute the real hook against small Android/Xposed fixtures; no phone or root."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'modules/chatgpt-se-fix'
ECJ = ROOT / '.cache/android-build/ecj-3.39.0.jar'

FIXTURES = {
    'android/os/Build.java': '''package android.os;
public final class Build { public static String DEVICE="tapas";
public static class VERSION { public static int SDK_INT=33; } }''',
    'android/content/pm/PackageManager.java': '''package android.content.pm;
public class PackageManager { public boolean ese, uicc=true, fail;
public boolean hasSystemFeature(String name) {
 if(fail) throw new IllegalStateException("fixture unavailable");
 return name.endsWith(".ese") ? ese : name.endsWith(".uicc") && uicc;
} }''',
    'android/content/Context.java': '''package android.content;
public class Context { public android.content.pm.PackageManager packages;
 public Context(android.content.pm.PackageManager p) {packages=p;}
 public android.content.pm.PackageManager getPackageManager(){return packages;}
}''',
    'de/robv/android/xposed/IXposedHookLoadPackage.java': '''package de.robv.android.xposed;
public interface IXposedHookLoadPackage {
 void handleLoadPackage(de.robv.android.xposed.callbacks.XC_LoadPackage.LoadPackageParam p) throws Throwable;
}''',
    'de/robv/android/xposed/callbacks/XC_LoadPackage.java': '''package de.robv.android.xposed.callbacks;
public class XC_LoadPackage {public static class LoadPackageParam {
 public String packageName, processName; public ClassLoader classLoader;
} }''',
    'de/robv/android/xposed/XC_MethodHook.java': '''package de.robv.android.xposed;
public abstract class XC_MethodHook {
 public static class MethodHookParam {public Object thisObject; public Object[] args;}
 public class Unhook {}
 protected void beforeHookedMethod(MethodHookParam p) throws Throwable {}
 public void dispatch(MethodHookParam p) throws Throwable {beforeHookedMethod(p);}
}''',
    'de/robv/android/xposed/XposedBridge.java': '''package de.robv.android.xposed;
public class XposedBridge {public static int logs; public static boolean fail;
 public static void log(String s){logs++; if(fail)throw new IllegalStateException("logging");}
}''',
    'de/robv/android/xposed/XposedHelpers.java': '''package de.robv.android.xposed;
public class XposedHelpers {
 public static XC_MethodHook hook; public static boolean failInstall;
 public static XC_MethodHook.Unhook findAndHookMethod(String c,ClassLoader l,String m,Object... a){
  if(failInstall)throw new IllegalStateException("fixture missing method");
  if(!c.equals("com.android.se.Terminal")||!m.equals("initialize")||a.length!=2||a[0]!=boolean.class)
   throw new AssertionError("Unexpected method target");
  hook=(XC_MethodHook)a[1]; return null;
 }
 public static Object getObjectField(Object o,String n) throws Exception {
  java.lang.reflect.Field f=o.getClass().getDeclaredField(n);f.setAccessible(true);return f.get(o);
 }
}''',
    'Harness.java': '''import android.os.Build;
import android.content.Context;
import android.content.pm.PackageManager;
import de.robv.android.xposed.*;
import de.robv.android.xposed.callbacks.XC_LoadPackage;
import org.cloude.chatgpt.sefix.SeFix;
public class Harness {
 static class Terminal {private String mName;private Context mContext;
  Terminal(String n,Context c){mName=n;mContext=c;}}
 static int assertions;
 static void check(boolean value,String label){assertions++;if(!value)throw new AssertionError(label);}
 static XC_LoadPackage.LoadPackageParam params(String pkg,String process){
  XC_LoadPackage.LoadPackageParam p=new XC_LoadPackage.LoadPackageParam();
  p.packageName=pkg;p.processName=process;p.classLoader=Harness.class.getClassLoader();return p;}
 static void attempt(String terminal,boolean ese,boolean uicc,boolean retry,boolean expected) throws Throwable {
  PackageManager pm=new PackageManager();pm.ese=ese;pm.uicc=uicc;
  XC_MethodHook.MethodHookParam call=new XC_MethodHook.MethodHookParam();
  call.thisObject=new Terminal(terminal,new Context(pm));call.args=new Object[]{retry};
  XposedHelpers.hook.dispatch(call);check(call.args[0].equals(expected),terminal+" retry");}
 static void failSafe(Object terminal,String label) throws Throwable {
  XC_MethodHook.MethodHookParam call=new XC_MethodHook.MethodHookParam();
  call.thisObject=terminal;call.args=new Object[]{true};XposedHelpers.hook.dispatch(call);
  check(Boolean.TRUE.equals(call.args[0]),label);}
 public static void main(String[] args) throws Throwable {
  SeFix fix=new SeFix();
  fix.handleLoadPackage(params("com.whatsapp","com.whatsapp"));check(XposedHelpers.hook==null,"unrelated app");
  fix.handleLoadPackage(params("com.android.se","com.android.se:other"));check(XposedHelpers.hook==null,"other process");
  Build.DEVICE="topaz";fix.handleLoadPackage(params("com.android.se","com.android.se"));check(XposedHelpers.hook==null,"other device");
  Build.DEVICE="tapas";Build.VERSION.SDK_INT=34;fix.handleLoadPackage(params("com.android.se","com.android.se"));check(XposedHelpers.hook==null,"other Android");
  Build.VERSION.SDK_INT=33;XposedHelpers.failInstall=true;
  fix.handleLoadPackage(params("com.android.se","com.android.se"));check(XposedHelpers.hook==null,"missing method");
  XposedHelpers.failInstall=false;fix.handleLoadPackage(params("com.android.se","com.android.se"));
  check(XposedHelpers.hook!=null,"eligible hook installed");
  attempt("eSE1",false,true,true,false);
  attempt("SIM1",false,true,true,true);attempt("SIM2",false,true,true,true);
  attempt("eSE2",false,true,true,true);attempt("eSE1",true,true,true,true);
  attempt("eSE1",false,false,true,true);attempt("eSE1",false,true,false,false);
  failSafe(new Object(),"missing fields");failSafe(new Terminal("eSE1",null),"missing context");
  failSafe(new Terminal("eSE1",new Context(null)),"missing package manager");
  PackageManager bad=new PackageManager();bad.fail=true;
  failSafe(new Terminal("eSE1",new Context(bad)),"feature lookup failure");
  XposedBridge.fail=true;attempt("eSE1",false,true,true,false);
  System.out.println("PASS "+assertions+" hook guard assertions; no HAL or phone accessed");
 }
}''',
}


class SeFixTests(unittest.TestCase):
    @unittest.skipUnless(ECJ.exists(), 'Requires the pinned ECJ Android build toolchain')
    def test_actual_hook_guards_and_failure_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = []
            for name, contents in FIXTURES.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)
                sources.append(str(path))
            classes = root / 'classes'
            sources.append(str(PROJECT / 'src/main/java/org/cloude/chatgpt/sefix/SeFix.java'))
            result = subprocess.run(['java', '-jar', str(ECJ), '-8', '-proc:none', '-d', str(classes), *sources], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run(['java', '-cp', str(classes), 'Harness'], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS 18 hook guard assertions', result.stdout)

    def test_module_scope_and_permissions(self):
        android = '{http://schemas.android.com/apk/res/android}'
        manifest = ET.parse(PROJECT / 'src/main/AndroidManifest.xml').getroot()
        self.assertEqual(manifest.attrib['package'], 'org.cloude.chatgpt.sefix')
        self.assertEqual(manifest.findall('uses-permission'), [])
        app = manifest.find('application')
        self.assertEqual(app.findall('activity'), [])
        metadata = {x.attrib[android + 'name']: x.attrib for x in app.findall('meta-data')}
        self.assertEqual(metadata['xposedmodule'][android + 'value'], 'true')
        self.assertEqual(metadata['xposedminversion'][android + 'value'], '82')
        resources = PROJECT / 'src/main/res/values'
        scopes = []
        for file in resources.glob('*.xml'):
            for array in ET.parse(file).getroot().findall('string-array'):
                if array.attrib.get('name') == 'xposed_scope':
                    scopes.extend(x.text for x in array.findall('item'))
        self.assertEqual(scopes, ['com.android.se'])
        self.assertEqual((PROJECT / 'src/main/assets/xposed_init').read_text().strip(), 'org.cloude.chatgpt.sefix.SeFix')


if __name__ == '__main__':
    unittest.main()
