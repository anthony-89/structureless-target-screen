"""Orchestrator: chain the 8 modules, short-circuit on `unscreenable`.

The whole point of the status contract lives here: after each module we check
`can_continue`. An `unscreenable` result stops the pipeline and the manifest
records exactly where and why — the state an agent reasons over.
"""
from __future__ import annotations
import time
from .config import PipelineConfig
from .status import RunManifest, Status, unscreenable
from .modules import (m1_intake, m2_qc, m3_receptor, m4_site,
                      m5_validate, m6_library, m7_screen, m8_prioritize)


def _timed(fn, *a, **k):
    t0 = time.time()
    r = fn(*a, **k)
    r.elapsed_s = round(time.time() - t0, 2)
    return r


def run_pipeline(cfg: PipelineConfig, verbose: bool = True) -> RunManifest:
    man = RunManifest(target=cfg.target, modulator=cfg.modulator_name)

    def step(r):
        man.add(r)
        if verbose:
            print(r)
        return r

    # M1 intake
    m1 = step(_timed(m1_intake.run, cfg))
    if not m1.can_continue:
        return _finish(man, cfg, verbose)

    # M2 QC (confidence gate — low_confidence propagates, does not stop)
    m2 = step(_timed(m2_qc.run, cfg, m1))
    structure = next((a for a in m1.artifacts if a.endswith(".cif")), None)

    # M3 receptor prep
    m3 = step(_timed(m3_receptor.run, cfg, structure))
    if not m3.can_continue:
        return _finish(man, cfg, verbose)
    receptor_pdbqt = next((a for a in m3.artifacts if a.endswith(".pdbqt")), None)

    # M4 site definition (THE graceful-degradation gate)
    m4 = step(_timed(m4_site.run, cfg, receptor_pdbqt))
    if not m4.can_continue:
        return _finish(man, cfg, verbose)
    site = m4.data

    # M5 reference validation
    m5 = step(_timed(m5_validate.run, cfg, receptor_pdbqt, site))
    if not m5.can_continue:
        return _finish(man, cfg, verbose)
    anchor_kcal = m5.data.get("screen_benchmark_kcal_mol")
    upstream_low = (m2.status is Status.LOW_CONFIDENCE) or (m5.status is Status.LOW_CONFIDENCE) \
                   or (m4.status is Status.LOW_CONFIDENCE)

    # M6 library
    m6 = step(_timed(m6_library.run, cfg))
    if not m6.can_continue:
        return _finish(man, cfg, verbose)
    library_csv = next((a for a in m6.artifacts if a.endswith(".csv")), None)

    # M7 screen
    m7 = step(_timed(m7_screen.run, cfg, receptor_pdbqt, site, library_csv))
    if not m7.can_continue:
        return _finish(man, cfg, verbose)
    scores_csv = next((a for a in m7.artifacts if a.endswith(".csv")), None)

    # M8 prioritize
    step(_timed(m8_prioritize.run, cfg, scores_csv, library_csv,
                upstream_low_confidence=upstream_low, anchor_kcal=anchor_kcal))
    return _finish(man, cfg, verbose)


def _finish(man, cfg, verbose):
    path = man.save(str(cfg.path("run_manifest.json")))
    if verbose:
        print(f"\n== overall: {man.overall_status.value} "
              f"(reached {man.last.module if man.last else 'none'}) ==")
        print(f"manifest: {path}")
    return man
