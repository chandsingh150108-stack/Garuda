"""Phase 20 gate: study tooling — balanced randomization, known-statistic
reproduction, and seeded-reproducible intervals (all on synthetic data;
no participants involved)."""
import json

from evals.study import analysis as AN
from evals.study import randomize as RZ


def test_schedule_balanced_and_reproducible(tmp_path):
    first = RZ.schedule(8, seed=7)
    assert len(first) == 8
    mentor_first = sum(1 for r in first if r["session1_condition"] == "mentor")
    assert mentor_first == 4  # each condition first for half
    assert RZ.schedule(8, seed=7) == first  # recorded seed reproduces
    assert RZ.schedule(8, seed=8) != first
    sets = {(r["session1_set"], r["session2_set"]) for r in first}
    assert sets == {("X", "Y"), ("Y", "X")}
    out = tmp_path / "sched.csv"
    assert RZ.main(["--seed", "7", "--participants", "8",
                    "--out", str(out)]) == 0
    assert out.is_file()


def test_wilcoxon_reproduces_known_effect():
    mentor = [10.0, 12.0, 9.0, 11.0, 13.0, 10.0, 12.0, 11.0]
    baseline = [20.0, 22.0, 19.0, 21.0, 23.0, 20.0, 22.0, 21.0]
    res = AN.wilcoxon_signed_rank(mentor, baseline)
    assert res["n"] == 8 and res["median_diff"] == -10.0
    assert res["p_two_sided"] < 0.05  # uniform large effect
    tied = AN.wilcoxon_signed_rank([1.0, 1.0], [1.0, 1.0])
    assert tied["p_two_sided"] == 1.0 and tied["n"] == 0


def test_bootstrap_intervals_reproducible_and_covering():
    mentor = [10.0, 12.0, 9.0, 11.0, 13.0, 10.0]
    baseline = [20.0, 22.0, 19.0, 21.0, 23.0, 20.0]
    ci1 = AN.bootstrap_ci(mentor, baseline, seed=7)
    assert AN.bootstrap_ci(mentor, baseline, seed=7) == ci1
    assert ci1[0] <= -10.0 <= ci1[1]  # covers the true mean difference


def test_analysis_end_to_end_on_synthetic_sessions(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for i in range(4):
        doc = {"participant": f"P{i + 1:02d}",
               "mentor": {"time_s": 100 + i, "correct": 10,
                          "files_hit": 6, "draw": 3,
                          "confidence": 4, "sus": 80},
               "baseline": {"time_s": 200 + i, "correct": 6,
                            "files_hit": 4, "draw": 2,
                            "confidence": 3, "sus": 60}}
        (data / f"P{i + 1:02d}.json").write_text(json.dumps(doc),
                                                encoding="utf-8")
    report = AN.analyze(data, seed=7)
    assert report["n_files"] == 4
    assert report["metrics"]["correct"]["median_diff"] == 4.0
    assert "note" in report["metrics"]["correct"]  # n<6 flagged descriptive
    assert report["metrics"]["time_s"]["mean_diff"] < 0
