#!/usr/bin/env python3
"""Isolated Fcitx core tests and installer rollback tests."""
import argparse
import importlib.util
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_tools', ROOT / 'scripts/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def run(argv, **kwargs):
    subprocess.run([str(a) for a in argv], check=True, **kwargs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sysroot')
    p.add_argument('--x11', action='store_true', help='Also test temporary X11 windows on current DISPLAY')
    args = p.parse_args()
    flags, libs = build.toolchain(args.sysroot)
    out = ROOT / 'build/tests'
    out.mkdir(parents=True, exist_ok=True)
    common = ['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', *flags]
    with tempfile.TemporaryDirectory(prefix='wetypex-anchor-test-') as temporary:
        env = os.environ.copy()
        for key in ['FCITX_CONFIG_HOME', 'FCITX_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME']:
            directory = pathlib.Path(temporary) / key
            directory.mkdir()
            env[key] = str(directory)
        env['LD_PRELOAD'] = str(ROOT / 'build/libprekey-anchor.so')
        env.pop('FCITX_PREKEY_TRACE', None)
        for module in ['classicui', 'kimpanel']:
            run([*common, '-fPIC', '-shared', ROOT / 'tests/ui-probe.cpp', *libs, '-o', out / f'lib{module}.so'])
            run([*common, ROOT / 'tests/test-prekey.cpp', *libs, '-L', out, f'-l{module}', '-Wl,-rpath,$ORIGIN', '-o', out / f'test-{module}'])
            run([out / f'test-{module}'], env=env)
    # Real install/uninstall into a disposable home, including backup restoration.
    with tempfile.TemporaryDirectory(prefix='wetypex-install-test-') as temporary:
        home = pathlib.Path(temporary)
        existing = home / '.config/autostart/org.fcitx.Fcitx5.desktop'
        existing.parent.mkdir(parents=True)
        original = b'[Desktop Entry]\nName=Existing user configuration\n'
        existing.write_bytes(original)
        run(['python3', ROOT / 'scripts/install.py', '--stage-home', home])
        assert (home / '.local/bin/wetypex-gnome-stable').is_file()
        assert b'Hidden=true' in existing.read_bytes()
        run(['python3', ROOT / 'scripts/uninstall.py', '--stage-home', home])
        assert existing.read_bytes() == original
        assert not (home / '.local/bin/wetypex-gnome-stable').exists()
        print('PASS: staged installation, user-file backup, uninstall and restore')
    if args.x11:
        run(['cc', '-Wall', '-Wextra', '-Werror', ROOT / 'tests/test-window-anchor.c', '-lxcb', '-o', out / 'test-window-anchor'])
        env = os.environ.copy()
        env['LD_PRELOAD'] = str(ROOT / 'build/libcandidate-anchor.so')
        run([out / 'test-window-anchor'], env=env)
        run(['cc', '-Wall', '-Wextra', '-Werror', '-fPIC', '-shared', '-Dmain=anchor_test_main',
             ROOT / 'tests/test-window-anchor.c', '-lxcb', '-o', out / 'liblocal-xcb-test.so'])
        run(['cc', '-Wall', '-Wextra', '-Werror', ROOT / 'tests/local-xcb-loader.c', '-ldl', '-o', out / 'local-xcb-loader'])
        run([out / 'local-xcb-loader', out / 'liblocal-xcb-test.so'], env=env)
        print('PASS: XCB interception with RTLD_LOCAL UI module')

if __name__ == '__main__':
    main()
