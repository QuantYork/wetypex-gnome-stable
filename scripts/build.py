#!/usr/bin/env python3
"""Build only against the supported Fcitx ABI. Does not install system packages."""
import argparse
import pathlib
import shlex
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUPPORTED = '5.1.19'

def run(args):
    subprocess.run(args, check=True)

def toolchain(sysroot=None):
    runtime = subprocess.check_output(['fcitx5', '--version'], text=True).strip()
    if runtime != SUPPORTED:
        raise SystemExit(f'Supported Fcitx version: {SUPPORTED}; found {runtime}')
    if sysroot:
        root = pathlib.Path(sysroot).resolve()
        flags = [flag for folder in ['Core', 'Config', 'Utils']
                 for flag in ['-I', str(root / 'usr/include/Fcitx5' / folder)]]
        libs = ['-l:libFcitx5Core.so.7', '-l:libFcitx5Config.so.6', '-l:libFcitx5Utils.so.2']
    else:
        dev = subprocess.check_output(['pkg-config', '--modversion', 'Fcitx5Core'], text=True).strip()
        if dev != runtime:
            raise SystemExit(f'Header/runtime version mismatch: {dev}/{runtime}')
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'Fcitx5Core'], text=True))
        libs = shlex.split(subprocess.check_output(['pkg-config', '--libs', 'Fcitx5Core'], text=True))
    return flags, libs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sysroot', help='Developer-only extracted matching Fcitx dev packages')
    args = parser.parse_args()
    flags, libs = toolchain(args.sysroot)
    out = ROOT / 'build'
    out.mkdir(exist_ok=True)
    run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-fPIC', '-shared',
         str(ROOT / 'src/prekey-anchor.cpp'), *flags, '-Wl,-z,defs', *libs, '-ldl',
         '-o', str(out / 'libprekey-anchor.so')])
    run(['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror', '-fPIC', '-shared',
         str(ROOT / 'src/window-anchor.c'), '-ldl', '-Wl,--no-as-needed', '-lxcb', '-Wl,--as-needed', '-o', str(out / 'libcandidate-anchor.so')])
    (out / 'fcitx-version').write_text(SUPPORTED + '\n')
    print(f'Built for Fcitx {SUPPORTED}: {out}')

if __name__ == '__main__':
    main()
