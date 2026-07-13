"""Smoke + contract tests. Run: pytest -q  (or: python -m pytest)

These run offline against the cached example runs in examples/, exercising the same
code path as a live run. They assert the *status contract*, not specific chemistry.
"""
import json
from pathlib import Path
import pytest

from structure_to_screen import PipelineConfig, run_pipeline
from structure_to_screen.status import Status
from structure_to_screen.modules import m4_site
from structure_to_screen import _site_ensemble as ens

REPO = Path(__file__).resolve().parents[1]
OPLAH = "Nc1ncnc2c1ncn2[C@@H]1O[C@H](COP(=O)([O-])[O-])[C@@H](O)[C@H]1O"
AMP_BOX = [-16.2, -1.65, 15.2]


def _oplah_cfg(tmp):
    # copy the cached OPLAH run into a tmp workdir so tests don't mutate examples/
    import shutil
    wd = tmp / "oplah"
    shutil.copytree(REPO / "examples" / "oplah_run", wd)
    return PipelineConfig(target="O14841", modulator_smiles=OPLAH,
                          modulator_name="5-AMP", modulator_mode="activator", workdir=str(wd))


def test_oplah_cascade_low_confidence(tmp_path):
    man = run_pipeline(_oplah_cfg(tmp_path), verbose=False)
    assert man.overall_status is Status.LOW_CONFIDENCE
    assert man.last.module == "M8_prioritize"
    m5 = next(r for r in man.results if r.module == "M5_validate")
    assert m5.status is Status.LOW_CONFIDENCE
    assert m5.data["pose_trust"] == pytest.approx(0.59, abs=0.05)


def test_every_module_returns_a_status(tmp_path):
    man = run_pipeline(_oplah_cfg(tmp_path), verbose=False)
    for r in man.results:
        assert r.status in (Status.OK, Status.LOW_CONFIDENCE, Status.UNSCREENABLE)
        assert isinstance(r.reason, str) and r.reason


def test_no_site_proposer_yields_anything_is_unscreenable(tmp_path, monkeypatch):
    """Ensemble contract: when NO proposer produces a candidate (no homolog, no fpocket
    binary, no DiffDock poses), M4 is unscreenable with the honest none_found payload."""
    cfg = _oplah_cfg(tmp_path)
    (cfg.path("m4", "binding_site.json")).unlink(missing_ok=True)
    # homolog off; fpocket/diffdock contribute nothing in the offline test env
    monkeypatch.setattr(m4_site, "_search_liganded_homologs", lambda cfg, rec: [])
    monkeypatch.setattr(ens, "fpocket_propose", lambda cfg, rec: [])
    monkeypatch.setattr(ens, "diffdock_propose", lambda cfg, rec: [])
    man = run_pipeline(cfg, verbose=False)
    assert man.overall_status is Status.UNSCREENABLE
    m4 = next(r for r in man.results if r.module == "M4_site")
    assert m4.data["pocket_source"] == "none_found"
    assert "next_actions" in m4.data
    # short-circuit: nothing after M4
    assert not any(r.module.startswith("M5") for r in man.results)


def _stub_proposal(source, center, residues, conf=0.6):
    return ens.SiteProposal(source=source, box_center=list(center),
                            site_residues=list(residues), method_conf=conf)


def test_ensemble_selects_fpocket_when_no_homolog(tmp_path, monkeypatch):
    """The intended new capability: with no liganded homolog, fpocket localises the
    site and the modulator's own dock validates it (single method -> low_confidence)."""
    cfg = PipelineConfig(target="O14841", modulator_smiles=OPLAH, modulator_name="5-AMP",
                         workdir=str(tmp_path / "e1"))
    monkeypatch.setattr(m4_site, "_search_liganded_homologs", lambda cfg, rec: [])
    monkeypatch.setattr(ens, "fpocket_propose",
                        lambda cfg, rec: [_stub_proposal("fpocket", AMP_BOX, [13, 15, 16, 17, 18, 20, 34])])
    monkeypatch.setattr(ens, "diffdock_propose", lambda cfg, rec: [])
    monkeypatch.setattr(ens, "_prepare_modulator", lambda cfg: "stub.pdbqt")
    monkeypatch.setattr(ens, "_dock_modulator",
                        lambda cfg, rec, lig, center, size, resis, source: (-8.6, 0.86, 0.5))
    r = m4_site.run(cfg, "receptor.pdbqt")
    assert r.status is Status.LOW_CONFIDENCE           # only one method agreed
    assert r.data["pocket_source"] == "fpocket"
    assert r.data["box_center"] == AMP_BOX
    assert r.data["selection"]["modulator_coverage"] == 0.86


def test_ensemble_consensus_is_ok(tmp_path, monkeypatch):
    """Two independent methods agreeing on the site + a strong modulator dock -> ok."""
    cfg = PipelineConfig(target="O14841", modulator_smiles=OPLAH, workdir=str(tmp_path / "e2"))
    monkeypatch.setattr(m4_site, "_search_liganded_homologs", lambda cfg, rec: [])
    monkeypatch.setattr(ens, "fpocket_propose",
                        lambda cfg, rec: [_stub_proposal("fpocket", AMP_BOX, [13, 15, 16, 17, 18, 20, 34])])
    monkeypatch.setattr(ens, "diffdock_propose",
                        lambda cfg, rec: [_stub_proposal("diffdock", [-15.8, -1.2, 15.6], [16, 17, 18])])
    monkeypatch.setattr(ens, "_prepare_modulator", lambda cfg: "stub.pdbqt")
    monkeypatch.setattr(ens, "_dock_modulator",
                        lambda cfg, rec, lig, center, size, resis, source: (-8.6, 0.9, 0.7))
    r = m4_site.run(cfg, "receptor.pdbqt")
    assert r.status is Status.OK
    assert r.data["selection"]["consensus_n_methods_agreeing"] >= 1
    # the losing method is reported, not discarded
    assert len(r.data["runner_up_sites"]) == 1
    assert r.data["runner_up_sites"][0]["confidence_flag"] == "viable"


def test_ensemble_unscreenable_when_modulator_rejects_all(tmp_path, monkeypatch):
    """Candidates exist but the modulator engages none -> honest unscreenable."""
    cfg = PipelineConfig(target="O14841", modulator_smiles=OPLAH, workdir=str(tmp_path / "e3"))
    monkeypatch.setattr(m4_site, "_search_liganded_homologs", lambda cfg, rec: [])
    monkeypatch.setattr(ens, "fpocket_propose",
                        lambda cfg, rec: [_stub_proposal("fpocket", AMP_BOX, [13, 15, 16])])
    monkeypatch.setattr(ens, "diffdock_propose", lambda cfg, rec: [])
    monkeypatch.setattr(ens, "_prepare_modulator", lambda cfg: "stub.pdbqt")
    monkeypatch.setattr(ens, "_dock_modulator",
                        lambda cfg, rec, lig, center, size, resis, source: (None, 0.0, 0.0))
    r = m4_site.run(cfg, "receptor.pdbqt")
    assert r.status is Status.UNSCREENABLE
    assert r.data["pocket_source"] == "none_found"
    assert "engaged none" in r.data["reason"]
    # the rejected candidate is still surfaced
    assert r.data["runner_up_sites"][0]["confidence_flag"] == "rejected"


def _min_sdf():
    """A 2-atom V2000 SDF with correct 10-char coordinate fields (centroid = [-15.7,-1.65,15.2])."""
    a1 = f"{-16.2:10.4f}{-1.65:10.4f}{15.2:10.4f} C   0  0"
    a2 = f"{-15.2:10.4f}{-1.65:10.4f}{15.2:10.4f} O   0  0"
    return ("mol\n  prog\ncomment\n"
            "  2  1  0  0  0  0  0  0  0  0999 V2000\n"
            f"{a1}\n{a2}\n  1  2  1  0\nM  END\n$$$$\n")


def test_diffdock_proposer_pose_sources(tmp_path):
    """DiffDock proposer is non-blocking by default and resumable from its per-run cache."""
    # (1) run disabled, no poses -> contributes nothing (never blocks)
    cfg = PipelineConfig(target="O14841", modulator_smiles=OPLAH, modulator_name="5-AMP",
                         workdir=str(tmp_path / "d1"))
    assert ens._find_diffdock_poses(cfg, "receptor.pdbqt") == []

    # (2) poses already in the per-run cache -> reused, no run
    cfg2 = PipelineConfig(target="O14841", modulator_smiles=OPLAH, modulator_name="5-AMP",
                          workdir=str(tmp_path / "d2"))
    cache = cfg2.path("m4", "diffdock", ens._diffdock_complex_name(cfg2))
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "rank1_confidence-0.98.sdf").write_text(_min_sdf())
    got = ens._find_diffdock_poses(cfg2, "receptor.pdbqt")
    assert len(got) == 1 and got[0].endswith("rank1_confidence-0.98.sdf")
    props = ens.diffdock_propose(cfg2, None)          # None receptor -> centroid only, residues []
    assert props and props[0].source == "diffdock"
    assert props[0].box_center == [-15.7, -1.65, 15.2]


def test_unknown_target_unscreenable(tmp_path):
    cfg = PipelineConfig(target="ZZZZZZ", modulator_smiles="CCO",
                         modulator_name="x", workdir=str(tmp_path / "bad"))
    man = run_pipeline(cfg, verbose=False)
    assert man.overall_status is Status.UNSCREENABLE
    assert man.last.module == "M1_intake"
