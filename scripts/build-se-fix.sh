#!/usr/bin/env bash
# Build a separately signed, experimental LSPosed APK. Never modifies a phone.
set -euo pipefail
SE_FIX_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export SE_FIX_ROOT
exec python3 - <<'PY'
from pathlib import Path
import concurrent.futures
import hashlib
import json
import os
import re
import struct
import subprocess
import tempfile
import urllib.request
import zipfile

root = Path(os.environ['SE_FIX_ROOT'])
project = root / 'modules/chatgpt-se-fix'
tools = Path(os.environ.get('SE_FIX_TOOLS', root / '.cache/android-build'))
out = root / 'out/se-fix'
dist = root / 'dist'
for folder in (tools, out, dist):
    folder.mkdir(parents=True, exist_ok=True)
os.umask(0o077)

downloads = [
    {'file': 'build-tools_r35_linux.zip',
     'url': 'https://dl.google.com/android/repository/build-tools_r35_linux.zip',
     'sha256': 'bd3a4966912eb8b30ed0d00b0cda6b6543b949d5ffe00bea54c04c81e1561d88'},
    {'file': 'platform-33-ext3_r03.zip',
     'url': 'https://dl.google.com/android/repository/platform-33-ext3_r03.zip',
     'sha256': 'b32b10f787867987f03ae8e101d217e053a9065b7136379fb353b388379aed1d'},
    {'file': 'ecj-3.39.0.jar',
     'url': 'https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.39.0/ecj-3.39.0.jar',
     'sha256': '01f5a92ac19bb2b3bf85e295a68f2c73c264369109158b566ce9b490af982948'},
]

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fetch(item):
    path = tools / item['file']
    if not path.exists():
        temporary = path.with_suffix(path.suffix + '.partial')
        with urllib.request.urlopen(item['url'], timeout=90) as response, temporary.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        temporary.replace(path)
    if sha256(path) != item['sha256']:
        raise SystemExit('Toolchain checksum mismatch: ' + item['file'])
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                if not (tools / entry.filename).resolve().is_relative_to(tools.resolve()):
                    raise SystemExit('Unsafe toolchain archive path')
            archive.extractall(tools)
            for entry in archive.infolist():
                mode = (entry.external_attr >> 16) & 0o777
                if mode:
                    os.chmod(tools / entry.filename, mode)
    return item

print('Checking pinned Android build tools...', flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(fetch, downloads))

android_jar = tools / 'android-13/android.jar'
build_tools = tools / 'android-15'
ecj = tools / 'ecj-3.39.0.jar'
apksigner = build_tools / 'lib/apksigner.jar'
key = Path(os.environ.get('SE_FIX_KEYSTORE', tools / 'chatgpt-sefix-debug.p12'))
alias = os.environ.get('SE_FIX_KEY_ALIAS', 'chatgpt-sefix')
environment = dict(os.environ)
environment.setdefault('SE_FIX_KEY_PASSWORD', 'android')

source_paths = sorted(path for path in project.rglob('*') if path.is_file())
if not source_paths:
    raise SystemExit('Missing module sources: ' + str(project))
sources = {str(path.relative_to(root)): sha256(path) for path in source_paths}
sources['scripts/build-se-fix.sh'] = sha256(root / 'scripts/build-se-fix.sh')
source_digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
log = out / 'build.log'
log.write_text('ChatGPT SE Fix local build\n')

def run(arguments, label):
    result = subprocess.run([str(arg) for arg in arguments], env=environment,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    with log.open('a') as stream:
        stream.write('\n=== ' + label + ' ===\n' + result.stdout)
    if result.returncode:
        raise SystemExit(f'{label} failed (exit {result.returncode}); see {log}')
    return result.stdout

if not key.exists():
    key.parent.mkdir(parents=True, exist_ok=True)
    run(['keytool', '-genkeypair', '-keystore', key, '-storetype', 'PKCS12',
         '-storepass:env', 'SE_FIX_KEY_PASSWORD', '-keypass:env', 'SE_FIX_KEY_PASSWORD',
         '-alias', alias, '-dname', 'CN=ChatGPT SecureElement Fix Experimental',
         '-keyalg', 'RSA', '-keysize', '3072', '-validity', '3650'], 'Create separate project signing key')
    key.chmod(0o600)

with tempfile.TemporaryDirectory(prefix='build-', dir=out) as directory:
    work = Path(directory)
    api_classes = work / 'api-classes'
    app_classes = work / 'app-classes'
    dex = work / 'dex'
    for folder in (api_classes, app_classes, dex):
        folder.mkdir()
    api_sources = sorted((project / 'compile-only/java').rglob('*.java'))
    app_sources = sorted((project / 'src/main/java').rglob('*.java'))
    if not api_sources or not app_sources:
        raise SystemExit('Expected Java sources in compile-only/java and src/main/java')
    compiler = ['java', '-jar', ecj, '-source', '8', '-target', '8', '-proc:none',
                '-bootclasspath', android_jar]
    run(compiler + ['-d', api_classes] + api_sources, 'Compile API-only descriptors')
    run(compiler + ['-classpath', api_classes, '-d', app_classes] + app_sources,
        'Compile module Java')

    epoch = int(os.environ.get('SOURCE_DATE_EPOCH', '1792713600'))
    import datetime
    zip_date = datetime.datetime.fromtimestamp(max(epoch, 315532800), datetime.timezone.utc).timetuple()[:6]

    def archive_classes(folder, target):
        with zipfile.ZipFile(target, 'w') as archive:
            for path in sorted(folder.rglob('*.class')):
                entry = zipfile.ZipInfo(str(path.relative_to(folder)), date_time=zip_date)
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, path.read_bytes())

    api_jar = work / 'compile-only.jar'
    app_jar = work / 'module.jar'
    archive_classes(api_classes, api_jar)
    archive_classes(app_classes, app_jar)
    run(['java', '-cp', build_tools / 'lib/d8.jar', 'com.android.tools.r8.D8',
         '--min-api', '33', '--lib', android_jar, '--classpath', api_jar,
         '--output', dex, app_jar], 'Convert module classes only to DEX')

    resources = work / 'resources.zip'
    unsigned = work / 'unsigned.apk'
    normalized = work / 'normalized.apk'
    aligned = work / 'aligned.apk'
    run([build_tools / 'aapt2', 'compile', '--dir', project / 'src/main/res', '-o', resources],
        'Compile module resources')
    run([build_tools / 'aapt2', 'link', '-I', android_jar, '--manifest',
         project / 'src/main/AndroidManifest.xml', '-o', unsigned, resources],
        'Link manifest and resources')
    with zipfile.ZipFile(unsigned, 'a') as archive:
        for path in sorted(dex.glob('classes*.dex')):
            entry = zipfile.ZipInfo(path.name, date_time=zip_date)
            archive.writestr(entry, path.read_bytes())
        for path in sorted((project / 'src/main/assets').rglob('*')):
            if path.is_file():
                entry = zipfile.ZipInfo('assets/' + str(path.relative_to(project / 'src/main/assets')),
                                        date_time=zip_date)
                archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(unsigned) as origin, zipfile.ZipFile(normalized, 'w') as target:
        for name in sorted(origin.namelist()):
            entry = origin.getinfo(name)
            entry.date_time = zip_date
            target.writestr(entry, origin.read(name))
    run([build_tools / 'zipalign', '-f', '-p', '4', normalized, aligned], 'Align APK')
    apk = dist / 'ChatGPT-SE-Fix-0.1.0-rc1.apk'
    run(['java', '-jar', apksigner, 'sign', '--ks', key, '--ks-key-alias', alias,
         '--ks-pass', 'env:SE_FIX_KEY_PASSWORD', '--key-pass', 'env:SE_FIX_KEY_PASSWORD',
         '--out', apk, aligned], 'Sign separate experimental module')

verification = run(['java', '-jar', apksigner, 'verify', '--verbose', '--print-certs', apk],
                   'Verify APK signature')
run([build_tools / 'zipalign', '-c', '-p', '4', apk], 'Verify alignment')
badging = run([build_tools / 'aapt2', 'dump', 'badging', apk], 'Verify package metadata')
class_definitions = []
with zipfile.ZipFile(apk) as archive:
    for name in archive.namelist():
        if not re.fullmatch(r'classes\d*\.dex', name):
            continue
        data = archive.read(name)
        string_count, string_offset = struct.unpack_from('<II', data, 56)
        _, type_offset = struct.unpack_from('<II', data, 64)
        class_count, class_offset = struct.unpack_from('<II', data, 96)
        for index in range(class_count):
            type_index = struct.unpack_from('<I', data, class_offset + index * 32)[0]
            string_index = struct.unpack_from('<I', data, type_offset + type_index * 4)[0]
            if string_index >= string_count:
                raise SystemExit('Invalid DEX string index')
            offset = struct.unpack_from('<I', data, string_offset + string_index * 4)[0]
            while data[offset] & 0x80:
                offset += 1
            offset += 1
            descriptor = data[offset:data.index(0, offset)].decode('utf-8')
            if descriptor.startswith('Lde/robv/android/xposed/'):
                raise SystemExit('Compile-only Xposed descriptor was accidentally packaged')
            class_definitions.append(descriptor)
certificate = re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-f]+)', verification)
manifest = {
    'artifact': apk.name,
    'sha256': sha256(apk),
    'bytes': apk.stat().st_size,
    'certificate_sha256': certificate.group(1) if certificate else None,
    'source_digest_sha256': source_digest,
    'sources': sources,
    'tools': downloads,
    'java': run(['java', '-version'], 'Java version').strip(),
    'source_date_epoch': epoch,
    'signature_verified': True,
    'alignment_verified': True,
    'hardware_tested': False,
    'compile_only_descriptors_in_dex': False,
    'dex_class_definitions': sorted(class_definitions),
    'package_badging': badging.splitlines(),
}
manifest_path = dist / 'ChatGPT-SE-Fix-0.1.0-rc1-build.json'
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print('Built:', apk)
print('SHA-256:', manifest['sha256'])
print('Signing certificate SHA-256:', manifest['certificate_sha256'])
print('Manifest:', manifest_path)
print('Not tested on a phone; no phone settings were changed.')
PY
