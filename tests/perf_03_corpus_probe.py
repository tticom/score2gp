"""Windows PERF-03 stage probe; private outputs remain under ignored work/.

Run ``python tests/perf_03_corpus_probe.py before INDEX [BASE_SRC_SNAPSHOT]``
and repeat with ``after INDEX``. Indices 0/1/2 are the 34/6/2-page controls;
the remaining PDFs follow in filename order. Measure all indices, then run
``python tests/perf_03_corpus_probe.py compare before after``.
``python tests/perf_03_corpus_probe.py mutant BASE_SHA`` restores only _runs
in a fresh process and must exit 1 with both real-contour cases failing.
``python tests/perf_03_corpus_probe.py profile INDEX PAGE`` profiles one real
page of duration reading for the remaining Python-kernel candidate shares.
Wall times include wrapper/sampler overhead; stage RSS peaks are sampled at
20 ms and are absolute process working sets, not allocation deltas. Nested
duration preservation passes are included once in the duration stage.
No sidecar, reference, budget, allowance or output option is changed.
"""

import ctypes
import ast
from ctypes import wintypes
import functools
import filecmp
import hashlib
import importlib
import json
import sys
import subprocess
import threading
import time
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
module_root = (sys.argv[3] if len(sys.argv) > 3 and sys.argv[1] not in ('compare', 'mutant', 'profile')
               else str(ROOT / 'src'))
sys.path.insert(0, module_root)
from typer.testing import CliRunner


def compare(before, after):
    left = ROOT / 'work/perf03' / before
    right = ROOT / 'work/perf03' / after
    expected = {p.name for p in left.iterdir() if (p / 'receipt.json').exists()}
    actual = {p.name for p in right.iterdir() if (p / 'receipt.json').exists()}
    assert expected == actual and len(expected) == len(list((ROOT / 'fixtures/private').glob('*.pdf')))
    converted = 0
    for index in sorted(expected, key=int):
        old = json.loads((left / index / 'receipt.json').read_text(encoding='utf-8'))
        new = json.loads((right / index / 'receipt.json').read_text(encoding='utf-8'))
        for key in ('exit_code', 'hashes', 'status'):
            assert old[key] == new[key], f'source {index}: changed {key}'
        for relative in ('conversion/note-durations.json', 'conversion/tab/tab_raw.json'):
            old_path, new_path = left / index / relative, right / index / relative
            assert old_path.exists() == new_path.exists(), f'source {index}: artifact presence changed'
            if old_path.exists():
                assert filecmp.cmp(old_path, new_path, shallow=False), f'source {index}: changed artifact bytes'
        if old['status']['output_written']:
            with ZipFile(left / index / 'result.gp') as old_gp, ZipFile(right / index / 'result.gp') as new_gp:
                assert old_gp.read('Content/score.gpif') == new_gp.read('Content/score.gpif'), f'source {index}: changed GPIF bytes'
        converted += old['status']['output_written'] is True
        # Compare the entire report and warning payload, normalizing only the
        # run directory and import-path provenance of a baseline source snapshot.
        for relative in ('report.json', 'conversion/warnings.json'):
            payloads = []
            for directory in (left / index, right / index):
                path = directory / relative
                if not path.exists():
                    payloads.append(None)
                    continue
                payload = json.loads(path.read_text(encoding='utf-8'))
                if relative == 'report.json':
                    payload.pop('python_import_path', None)
                serialized = json.dumps(payload, sort_keys=True)
                serialized = serialized.replace(json.dumps(str(directory))[1:-1], '<RUN>')
                payloads.append(serialized)
            assert payloads[0] == payloads[1], f'source {index}: changed {relative}'
    print(json.dumps({'sources':len(expected), 'converted':converted,
                      'artifact_status_refusal_changes':0}))


if sys.argv[1] == 'compare':
    compare(sys.argv[2], sys.argv[3])
    raise SystemExit(0)

if sys.argv[1] == 'mutant':
    import pytest
    from score2gp.notation_omr import note_duration as reader

    baseline = subprocess.check_output([
        'git', 'show', sys.argv[2] + ':src/score2gp/notation_omr/note_duration.py'])
    tree = ast.parse(baseline)
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == '_runs')
    exec(compile(ast.Module(body=[function], type_ignores=[]),
                 '<REVERT_SCANLINE_CROSSINGS>', 'exec'), vars(reader))
    raise SystemExit(pytest.main(['tests/test_perf_03.py', '-k', 'contour', '-q']))

class Counters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
        'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
        'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
handle = ctypes.windll.kernel32.GetCurrentProcess()
ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
def memory():
    counters = Counters()
    ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), ctypes.sizeof(counters))
    return counters.WorkingSetSize

phase, source_index = sys.argv[1:3]
names = ['Melodic_Expressions.pdf', 'Lesson-6.pdf', 'Melodic_Expressions_Chap_19_.pdf']
names += [p.name for p in sorted((ROOT / 'fixtures/private').glob('*.pdf')) if p.name not in names]
source = ROOT / 'fixtures/private' / names[int(source_index)]
if phase == 'profile':
    import cProfile
    import pstats
    from score2gp.notation_omr.note_duration import read_note_durations

    page = int(sys.argv[3])
    profiler = cProfile.Profile()
    profiler.runcall(read_note_durations, source, pages=(page, page), time_signature=(4, 4))
    (ROOT / 'work').mkdir(exist_ok=True)
    profiler.dump_stats(str(ROOT / 'work/perf03-duration.prof'))
    pstats.Stats(profiler).sort_stats('cumtime').print_stats(35)
    raise SystemExit(0)
scratch = ROOT / 'work/perf03' / phase / source_index
scratch.mkdir(parents=True, exist_ok=True)
stages = {}
active = 'other'
stop = threading.Event()
def sample():
    while not stop.is_set():
        name = active
        item = stages.setdefault(name, {'seconds': 0., 'peak_rss_bytes': 0})
        item['peak_rss_bytes'] = max(item['peak_rss_bytes'], memory())
        stop.wait(.02)

def instrument(module, attr, name):
    original = getattr(module, attr)
    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        global active
        if active == name:
            return original(*args, **kwargs)
        previous = active
        active = name
        start = time.perf_counter()
        item = stages.setdefault(name, {'seconds': 0., 'peak_rss_bytes': 0})
        item['peak_rss_bytes'] = max(item['peak_rss_bytes'], memory())
        try:
            return original(*args, **kwargs)
        finally:
            item['seconds'] += time.perf_counter() - start
            item['peak_rss_bytes'] = max(item['peak_rss_bytes'], memory())
            active = previous
    setattr(module, attr, wrapper)

cli = importlib.import_module('score2gp.cli')
for attr, label in [('inspect_pdf_file','inspection'), ('extract_tab_file','extraction'),
                    ('write_gp','gp_write'), ('write_conversion_report','report')]:
    instrument(cli, attr, label)
for mod, attr, label in [
    ('notation_omr.note_duration','read_note_durations','duration'),
    ('build_ir','build_ir_from_tabraw_only','build_ir'),
    ('pdf','read_notation_barline_signals','barlines'),
]:
    module_name = 'score2gp.' + mod
    module = importlib.import_module(module_name)
    instrument(module, attr, label)

thread = threading.Thread(target=sample, daemon=True)
thread.start()
start = time.perf_counter()
result = CliRunner().invoke(cli.app, ['convert','--pdf',str(source), '--pdf-only-tab',
    '--time-signature','4/4', '--work-dir',str(scratch/'conversion'),
    '--out',str(scratch/'result.gp'), '--json-report',str(scratch/'report.json')])
elapsed = time.perf_counter() - start
stop.set()
thread.join()
stages['other']['seconds'] = elapsed - sum(v['seconds'] for k,v in stages.items() if k != 'other')
hashes = {}
for label, relative in [('durations','conversion/note-durations.json'), ('tabraw','conversion/tab/tab_raw.json')]:
    path = scratch / relative
    hashes[label] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
if (scratch/'result.gp').exists():
    with ZipFile(scratch/'result.gp') as package:
        hashes['gpif'] = hashlib.sha256(package.read('Content/score.gpif')).hexdigest()
report = json.loads((scratch/'report.json').read_text(encoding='utf-8')) if (scratch/'report.json').exists() else {}
receipt = {'source_index': int(source_index), 'phase': phase, 'seconds': elapsed,
    'peak_rss_bytes': max(v['peak_rss_bytes'] for v in stages.values()), 'stages': stages,
    'exit_code': result.exit_code, 'hashes': hashes,
    'status': {key:report.get(key) for key in ('status','stage','refusal_code','output_written')},
    'exception_type': type(result.exception).__name__ if result.exception else None}
(scratch/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
print(json.dumps(receipt), flush=True)
