#!/usr/bin/env python3
import importlib.util,pathlib
root=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('shortcuts',root/'scripts/extend-global-shortcuts.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
old='[ids]\n*\n\n[meta]\na = C-a\nc = C-c\nv = C-v\n\n[control]\n\n[control+meta]\na = C-M-a\n'
new=m.render(old)
assert m.render(new)==new
assert 'x = C-x\nz = C-z\n' in new
assert new.replace('x = C-x\nz = C-z\n','')==old
for bad in ['[ids]\n*\n',old.replace('[meta]','[meta]\nx = C-q')]:
 try:m.render(bad)
 except ValueError:pass
 else:raise AssertionError('Unexpected mapping accepted')
print('PASS: add cut/undo only, preserve existing mappings, idempotency, reject conflicting config')
