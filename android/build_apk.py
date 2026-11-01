#!/usr/bin/env python3
"""Builds HL.apk without the Android SDK.

Needs (all from Maven Central, see android/README.md): apktool-cli (aapt2 + framework resources),
android.jar (API stubs), dalvik-dx and apksig.   python3 android/build_apk.py <tools-dir> <work-dir>
"""
import os, shutil, subprocess, sys, zipfile, struct
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.abspath(sys.argv[1]); WORK = os.path.abspath(sys.argv[2])
OUT = os.path.join(ROOT, 'HL', 'HL.apk')
KS = os.path.join(HERE, 'hl.p12'); KSPASS = 'hlplanner'
AAPT2 = os.path.join(TOOLS, 'x/prebuilt/linux/aapt2')
FRAMEWORK = os.path.join(TOOLS, 'x/prebuilt/android-framework.jar')

def run(*cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        print(r.stdout, r.stderr); sys.exit('failed: ' + ' '.join(cmd[:3]))
    return r.stdout

shutil.rmtree(WORK, ignore_errors=True)
for d in ('res', 'compiled', 'classes', 'assets'): os.makedirs(os.path.join(WORK, d))
# ---- icons
ico = Image.open(os.path.join(ROOT, 'HL', 'HL.ico'))
big = ico.ico.getimage((256, 256)).convert('RGBA')
for name, px in (('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)):
    d = os.path.join(WORK, 'res', 'mipmap-' + name); os.makedirs(d)
    big.resize((px, px), Image.LANCZOS).save(os.path.join(d, 'ic_launcher.png'))
shutil.copy(os.path.join(ROOT, 'HL', 'HL.html'), os.path.join(WORK, 'assets', 'HL.html'))
# ---- resources + manifest
run(AAPT2, 'compile', '--dir', os.path.join(WORK, 'res'), '-o', os.path.join(WORK, 'compiled'))
flats = [os.path.join(WORK, 'compiled', f) for f in os.listdir(os.path.join(WORK, 'compiled'))]
base = os.path.join(WORK, 'base.apk')
run(AAPT2, 'link', '-o', base, '-I', FRAMEWORK, '--manifest', os.path.join(HERE, 'AndroidManifest.xml'),
    '-A', os.path.join(WORK, 'assets'), '--min-sdk-version', '29', '--target-sdk-version', '34',
    '--version-code', '51', '--version-name', '5.1', *flats)
# ---- code
src = os.path.join(HERE, 'src/com/heeseop/hl/MainActivity.java')
run('javac', '--release', '8', '-cp', os.path.join(TOOLS, 'android34.jar'), '-d', os.path.join(WORK, 'classes'), src)
run('java', '-cp', os.path.join(TOOLS, 'dx.jar'), 'com.android.dx.command.Main', '--dex',
    '--output=' + os.path.join(WORK, 'classes.dex'), os.path.join(WORK, 'classes'))
# ---- assemble: aapt2 output + classes.dex, resources.arsc stored + 4-byte aligned (zipalign-style)
unsigned = os.path.join(WORK, 'unsigned.apk')
src_zip = zipfile.ZipFile(base)
entries = [(i.filename, src_zip.read(i.filename)) for i in src_zip.infolist()]
entries.append(('classes.dex', open(os.path.join(WORK, 'classes.dex'), 'rb').read()))
with open(unsigned, 'wb') as raw:
    z = zipfile.ZipFile(raw, 'w')
    for name, data in entries:
        stored = name == 'resources.arsc' or name.endswith(('.png', '.dex', '.so'))
        zi = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        if stored:
            pos = raw.tell() + 30 + len(name.encode())
            pad = (-pos) % 4
            if pad:
                zi.extra = struct.pack('<HH', 0xD935, max(0, pad - 4)) + b'\0' * max(0, pad - 4) if pad >= 4 else b''
                if pad < 4:   # need >=4 bytes for an extra header; shift by 4 + (pad) so alignment still lands
                    pad += 4
                    zi.extra = struct.pack('<HH', 0xD935, pad - 4) + b'\0' * (pad - 4)
        z.writestr(zi, data)
    z.close()
# ---- sign
if not os.path.exists(KS):
    run('keytool', '-genkeypair', '-keystore', KS, '-storetype', 'PKCS12', '-storepass', KSPASS, '-alias', 'hl',
        '-keyalg', 'RSA', '-keysize', '2048', '-validity', '36500', '-dname', 'CN=HL Planner, O=HL, C=KR')
run('javac', '-cp', os.path.join(TOOLS, 'apksig.jar'), '-d', WORK, os.path.join(HERE, 'Sign.java'))
print(run('java', '--add-exports', 'java.base/sun.security.x509=ALL-UNNAMED', '--add-exports', 'java.base/sun.security.pkcs=ALL-UNNAMED', '--add-exports', 'java.base/sun.security.util=ALL-UNNAMED', '-cp', os.path.join(TOOLS, 'apksig.jar') + ':' + WORK, 'Sign', KS, KSPASS, unsigned, OUT).strip())
print(OUT, os.path.getsize(OUT) // 1024, 'KB')
