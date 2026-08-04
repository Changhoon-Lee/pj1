#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

PUBLIC_FINAL_COMMIT = "2e57eb2c7b0215ed7e59ee4338c730bf88aa9577"
TARGETS = [884503672, 756621450]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def zip_tree(src: Path, dst: Path, compression=zipfile.ZIP_DEFLATED) -> None:
    with zipfile.ZipFile(dst, "w", compression=compression, compresslevel=6 if compression == zipfile.ZIP_DEFLATED else None) as zf:
        for p in sorted(src.rglob("*")):
            if not p.is_file():
                continue
            info = zipfile.ZipInfo(p.relative_to(src.parent).as_posix(), (2026, 8, 4, 0, 0, 0))
            info.compress_type = compression
            info.external_attr = (0o755 if os.access(p, os.X_OK) else 0o644) << 16
            zf.writestr(info, p.read_bytes(), compress_type=compression)


def build_core(repo: Path, stage: Path) -> Path:
    project = stage / "PCS_CFSC_SAC_NATURE_PATH_HANDOFF_CORE_GEN7_V2R2"
    for d in [
        "00_START_HERE",
        "01_EXECUTIVE_HANDOFF",
        "02_EXTREME_HARSH_RED_TEAM",
        "03_CURRENT_GEN7_EVIDENCE",
        "04_NEXT_GENERATION",
        "05_INTEGRITY",
    ]:
        (project / d).mkdir(parents=True, exist_ok=True)

    write(project / "00_START_HERE" / "NEW_CHAT_FIRST_MESSAGE.txt", """ZIP을 풀고 이 파일을 최상위 권위 지시로 사용하세요.

1. `python 05_INTEGRITY/VERIFY_CORE.py`를 실행하세요.
2. `MASTER_HANDOFF.md`, `01_EXECUTIVE_HANDOFF/PROJECT_TIMELINE.md`,
   `02_EXTREME_HARSH_RED_TEAM/EXTREME_HARSH_RED_TEAM_AUDIT.md`를 읽으세요.
3. 현행 Gen7 결과를 제한된 범위 그대로 보존하세요.
4. 같은 scikit-learn workflow에 seed를 더 추가하지 마세요.
5. 다음 연구는 실제 decision-bearing scientific workflow, 외부 policy owner,
   independent B10, negative regime과 external independent reproduction을 갖는 Gen8이어야 합니다.

`01_CORE_HANDOFF.zip` 하나만으로 새 탭을 시작할 수 있습니다.
나머지 ZIP은 source·역사 보고서·대형 target bytes가 필요할 때만 추가하세요.
""")

    write(project / "MASTER_HANDOFF.md", f"""# MASTER HANDOFF — PCS → CFSC → SAC-RLSA

## 현행 권위 결과

```text
AUTHORITATIVE_VERDICT=
SAC_RLSA_30X_THEORY_CERTIFIED_PUBLIC_SOURCE_BOUND_WORKFLOW_CROSSOVER_ESTABLISHED

EVIDENCE_SCOPE=
PUBLIC_SOURCE_BOUND_SCALED_SHADOW_REGRESSION

PUBLIC_FINAL_COMMIT=
{PUBLIC_FINAL_COMMIT}

TARGETS=
{TARGETS[0]},{TARGETS[1]}
```

두 untouched targets는 full truth 전에 `30X_CERTIFIED`로 동결됐고,
Ubuntu x86-64와 macOS arm64에서 same target bytes, same report digest,
strict independent C++ raw truth, Decimal-40 canonical truth, same decision,
complete platform-specific B7와 30×/10× gates를 통과했다.

## 절대 금지 claim

- 모든 계산과학에서 30×
- 실제 기관 complete lifecycle 30×
- 외부 독립 연구팀 재현 완료
- 실제 decision-bearing science에서 확립
- Nature Computational Science submission-ready
- RLA·hypergraph·LP·KL 구성요소 자체의 절대 최초 발명

## 증거 우선순위

1. public Git commit `{PUBLIC_FINAL_COMMIT}`
2. CORE 내부 current Gen7 evidence snapshot
3. `02_CURRENT_SOURCE_AND_PUBLIC_EVIDENCE.zip`
4. `03_HISTORICAL_REPORTS.zip`
5. 선택적 target-byte volumes

Stale local summary와 존재하지 않는 commit을 가리키는 과거 M5 replay kit는 권위가 아니다.
""")

    write(project / "01_EXECUTIVE_HANDOFF" / "EXECUTIVE_SUMMARY.md", """# Executive Summary

프로젝트는 세 번 연구 객체를 바꿨다.

1. **PCS:** 동일 계산에 proof를 추가하는 경로는 proofless same-plan을 이길 수 없었다. Obligation factoring, evidence passport, VSSC/EMCS/PSKIR 계열은 strongest native/manual/generic baseline에서 parity 또는 loss였다.
2. **CFSC:** verifier asymmetry는 존재했지만 prover overhead, 실제 demand, predictor generalization, witness truth와 strongest B10 문제가 generic certificate-wrapper 경로를 닫았다.
3. **SAC-RLSA:** 모든 output을 증명하는 대신 최종 decision을 뒤집는 discrepancy만 risk-limit 아래 독립 감사하는 문제로 전환했다. Gen3–4에서 phase theory를 만들고 Gen5–6의 soundness·canonicalization 실패를 보존한 뒤 Gen7에서 제한적 prospective crossover를 확립했다.

가장 중요한 이론 후보:

> Scientific assurance cost is governed by the action hypergraph of decision-flipping discrepancies. In support-complete symmetric classes, q_D = Theta(N^gamma) implies optimal audit speedup Theta(N^gamma); more generally, fractional action-cover duality, correlation geometry, noisy survival and information-per-cost govern the phase.

현재 empirical support는 workflow family 1개와 target 2개뿐이다.
""")

    write(project / "01_EXECUTIVE_HANDOFF" / "PROJECT_TIMELINE.md", """# Project Timeline

## PCS
- Same-algorithm-plus-proof dominance 경계 확립.
- Materials obligation factoring: supported non-native relation 0, branch KILL.
- Evidence passport: buildability는 확인됐으나 generic typed/provenance/policy architecture parity.
- VSSC/EMCS/PSKIR: contract re-encoding, source-binding TCB, typed/translation/modular baseline parity 또는 loss.
- CCAS: attribution discipline은 유용하지만 operational breakthrough는 아님.

## CFSC
- 일부 exact kernel에서 verifier asymmetry 확인.
- Fused prover overhead가 producer economics를 광범위하게 통과하지 못함.
- Checkability predictor의 prospective generalization 실패.
- Expected-statement binding만으로는 witness truth를 보장하지 못해 false authorization 발생.
- Sound witness reconstruction 후 capability가 native/B10으로 귀속됐고 B10이 21/21에서 우세.

## SAC-RLSA
- Gen1: restricted finite-population theory; broad influence에서 primary full audit 수렴.
- Gen2: operational joint evidence 미확보; target 실행 미승인.
- Gen3: decision-flip support/action-hypergraph phase theory, finite 10×/30× witnesses.
- Gen4: exact integral classes, support-complete log tightness, noisy LP, sequential information lower bound.
- Gen5: prospective signal이나 float32 tree semantics failure — authoritative negative.
- Gen6: 두 target에서 강한 30× signal이나 canonical digest, report binding, strict bound, complete B7 결함 — exact confirmation 실패.
- Gen7 V2R2: corrected authority, history-only platform qualification, single-use chronology, public Freeze A/B/C, selected-before-full, canonical truth, complete B7 — restricted positive established.
""")

    write(project / "02_EXTREME_HARSH_RED_TEAM" / "EXTREME_HARSH_RED_TEAM_AUDIT.md", """# Extreme Harsh Red Team Audit

## 통과한 핵심 공격
- Policy/semantics가 report 전에 동결됨.
- Theory class·audit size·risk가 full truth 전에 동결됨.
- Selected audit가 full truth 전에 완료됨.
- 두 플랫폼의 target bytes·report digest·strict raw truth·Decimal-40 truth·mean·decision 일치.
- Complete B7 portfolio를 Ubuntu와 macOS 모두 실행.
- 모든 target/platform median >=30×, conservative p05/p95 >=10×.
- macOS sklearn raw-bit 차이를 숨기지 않고 diagnostic-only로 분리; scientific truth는 strict independent C++ + Decimal-40으로 고정.

## 아직 열린 publication blockers
1. Targets=2, workflow family=1, domain=1.
2. Public-source-bound scaled shadow regression은 live external scientific decision이 아님.
3. 두 플랫폼 모두 managed GitHub CI이며 external independent research team이 아님.
4. Computational audit-stage speedup은 institutional lifecycle speedup이 아님.
5. Decimal-40 adjudication 비용은 operational denominator에서 분리됨; complete lifecycle claim에서는 비용화 필요.
6. 각 target risk가 약 1%; joint family-wise 1%는 자동 성립하지 않음.
7. Novelty는 RLA, finite-population testing, hypergraph cover, LP duality, active testing, sequential information 선행연구와 구별해야 함.
8. 공식 release/기관 decision이 아니라 source-bound shadow workflow임.
9. 실제 scientific throughput·turnaround·discovery impact가 미측정.
10. External policy owner, adoption, maintenance/migration evidence 부재.

## 편집자 관점
`SERIOUS_RESTRICTED_SCOPE_CANDIDATE`, not submission-ready. 다음은 동일 benchmark seed 추가가 아니라 실제 decision-bearing workflow + negative regime + external replication이어야 한다.
""")

    claim = {
        "authoritative_verdict": "SAC_RLSA_30X_THEORY_CERTIFIED_PUBLIC_SOURCE_BOUND_WORKFLOW_CROSSOVER_ESTABLISHED",
        "evidence_scope": "PUBLIC_SOURCE_BOUND_SCALED_SHADOW_REGRESSION",
        "public_final_commit": PUBLIC_FINAL_COMMIT,
        "targets": TARGETS,
        "pretruth_30x_certified": "2/2",
        "cross_platform_canonical_truth": "ESTABLISHED",
        "complete_b7": "ESTABLISHED",
        "external_independent_team": "NOT_ESTABLISHED",
        "institutional_lifecycle": "NOT_ESTABLISHED",
        "nature_readiness": "SERIOUS_RESTRICTED_SCOPE_CANDIDATE_NOT_SUBMISSION_READY",
    }
    write(project / "CLAIM_LEDGER.json", json.dumps(claim, indent=2, sort_keys=True) + "\n")

    write(project / "04_NEXT_GENERATION" / "GEN8_NATURE_PATH_BLUEPRINT.md", """# Gen8 Nature Path Blueprint

같은 workflow에 seed를 더 추가하지 않는다.

Minimum design:
- actual decision-bearing scientific workflows >=3
- scientific domains >=2
- official external policy owner
- independent B10 truth path
- theory-certified positive regime >=1
- preregistered fragile/impossible regime >=1
- external independent team >=1
- public pretruth Freeze A/B/C
- complete computational and engineering lifecycle ledger
- critical false certification =0
- full-truth decision agreement =100%
- positive workflow median >=10×, conservative >=3×; flagship >=30× target
- fragile workflow는 이론 예측대로 near-full audit/escalation

핵심 시험은 structurally different workflow 사이의 prospective phase-classification validity다.
""")

    key_paths = [
        "sac_rlsa_gen7v2/freeze/FREEZE_A_V2_AUTHORITATIVE_DIRECT_SOURCE.json",
        "sac_rlsa_gen7v2/freeze/FREEZE_BC_BUNDLE_V2.json",
        "sac_rlsa_gen7v2/public_results/SELECTED_AGGREGATE.json",
        "sac_rlsa_gen7v2/public_results/CROSS_PLATFORM_FINAL_SUMMARY.json",
        *[f"sac_rlsa_gen7v2/state/STATE_{i}.json" for i in range(7)],
        "sac_rlsa_gen7v2/public_records/target_reports/GEN7V2R2_UNTOUCHED_SEED884503672.SCIENTIFIC_TARGET_REPORT.json",
        "sac_rlsa_gen7v2/public_records/target_reports/GEN7V2R2_UNTOUCHED_SEED756621450.SCIENTIFIC_TARGET_REPORT.json",
    ]
    for rel in key_paths:
        src = repo / rel
        if not src.is_file():
            raise RuntimeError(f"missing authoritative file: {rel}")
        shutil.copy2(src, project / "03_CURRENT_GEN7_EVIDENCE" / rel.replace("/", "__"))

    verify = """#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
manifest=root/'05_INTEGRITY'/'MANIFEST.sha256'
fail=[]
for line in manifest.read_text().splitlines():
    expected, rel=line.split('  ',1)
    p=root/rel
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
        fail.append(rel)
print(json.dumps({'pass':not fail,'checks':len(manifest.read_text().splitlines()),'failures':fail},indent=2))
raise SystemExit(1 if fail else 0)
"""
    write(project / "05_INTEGRITY" / "VERIFY_CORE.py", verify)
    os.chmod(project / "05_INTEGRITY" / "VERIFY_CORE.py", 0o755)

    manifest_lines = []
    for p in sorted(project.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.sha256":
            manifest_lines.append(f"{sha256_file(p)}  {p.relative_to(project).as_posix()}")
    write(project / "05_INTEGRITY" / "MANIFEST.sha256", "\n".join(manifest_lines) + "\n")
    return project


def build_source(repo: Path, stage: Path) -> Path:
    dst = stage / "CURRENT_SOURCE_AND_PUBLIC_EVIDENCE"
    shutil.copytree(repo / "sac_rlsa_gen7v2", dst / "sac_rlsa_gen7v2")
    wf = dst / ".github" / "workflows"
    wf.mkdir(parents=True)
    for p in (repo / ".github" / "workflows").glob("*gen7*"):
        if p.is_file():
            shutil.copy2(p, wf / p.name)
    return dst


def build_history(repo: Path, stage: Path) -> Path:
    dst = stage / "HISTORICAL_REPORTS"
    dst.mkdir()
    names = {
        "FINAL_STATUS.txt", "MASTER_HANDOFF.md", "THEORY.md", "PROOFS.md",
        "CLAIM_LEDGER.md", "NATURE_READINESS.md", "AUTHORITATIVE_BOUNDARIES.md",
        "RESULTS_REPORT.md", "NOVELTY_AUDIT.md", "NATURE_EDITORIAL_ASSESSMENT.md",
    }
    count = 0
    for p in sorted(repo.rglob("*")):
        if ".git" in p.parts or not p.is_file() or p.name not in names:
            continue
        target = dst / p.relative_to(repo)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        count += 1
    write(dst / "HISTORICAL_REPORT_INDEX.json", json.dumps({
        "files": count,
        "scope": "reports present in the current public repository tree",
        "limitation": "not a byte-complete replacement for artifacts lost with expired chat code-interpreter sessions",
    }, indent=2) + "\n")
    return dst


def build_target_volumes(target_root: Path, stage: Path, out: Path) -> dict:
    packed = stage / "GEN7_V2R2_TARGET_BYTES_REPACKED.zip"
    with zipfile.ZipFile(packed, "w", compression=zipfile.ZIP_STORED) as zf:
        for p in sorted(target_root.rglob("*")):
            if not p.is_file():
                continue
            info = zipfile.ZipInfo(p.relative_to(target_root).as_posix(), (2026, 8, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            zf.writestr(info, p.read_bytes(), compress_type=zipfile.ZIP_STORED)
    whole_sha = sha256_file(packed)
    whole_size = packed.stat().st_size
    piece_size = 60 * 1024 * 1024
    pieces = []
    with packed.open("rb") as f:
        while True:
            block = f.read(piece_size)
            if not block:
                break
            pieces.append(block)
    if len(pieces) > 8:
        raise RuntimeError(f"unexpected number of pieces: {len(pieces)}")
    for index, piece in enumerate(pieces, 1):
        volume = out / f"04_TARGET_EVIDENCE_VOL{index:02d}.zip"
        part_name = f"GEN7_TARGET_BYTES.part{index:02d}"
        with zipfile.ZipFile(volume, "w", compression=zipfile.ZIP_STORED) as zf:
            info = zipfile.ZipInfo(part_name, (2026, 8, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            zf.writestr(info, piece, compress_type=zipfile.ZIP_STORED)
            zf.writestr("VOLUME_INFO.json", json.dumps({
                "volume": index,
                "total_volumes": len(pieces),
                "part_name": part_name,
                "part_sha256": hashlib.sha256(piece).hexdigest(),
                "reassembled_zip_sha256": whole_sha,
                "reassembled_zip_bytes": whole_size,
            }, indent=2, sort_keys=True) + "\n")
    for index in range(len(pieces) + 1, 9):
        with zipfile.ZipFile(out / f"04_TARGET_EVIDENCE_VOL{index:02d}.zip", "w") as zf:
            zf.writestr("UNUSED_VOLUME.txt", "This volume is intentionally unused.\n")
    return {"target_volume_count": len(pieces), "target_reassembled_sha256": whole_sha, "target_reassembled_bytes": whole_size}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--target-artifact", default="target_artifact")
    parser.add_argument("--output", default="handoff_output")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    target_root = Path(args.target_artifact).resolve()
    out = Path(args.output).resolve()
    stage = repo / "handoff_split" / ".stage"
    shutil.rmtree(out, ignore_errors=True)
    shutil.rmtree(stage, ignore_errors=True)
    out.mkdir(parents=True)
    stage.mkdir(parents=True)

    core = build_core(repo, stage)
    source = build_source(repo, stage)
    history = build_history(repo, stage)
    zip_tree(core, out / "01_CORE_HANDOFF.zip")
    zip_tree(source, out / "02_CURRENT_SOURCE_AND_PUBLIC_EVIDENCE.zip")
    zip_tree(history, out / "03_HISTORICAL_REPORTS.zip")
    target_meta = build_target_volumes(target_root, stage, out)

    write(out / "REASSEMBLE_TARGET_EVIDENCE.sh", """#!/bin/sh
set -eu
rm -rf .target_parts GEN7_V2R2_TARGET_BYTES_REPACKED.zip
mkdir .target_parts
for z in 04_TARGET_EVIDENCE_VOL*.zip; do unzip -oq "$z" -d .target_parts; done
cat .target_parts/GEN7_TARGET_BYTES.part* > GEN7_V2R2_TARGET_BYTES_REPACKED.zip
sha256sum GEN7_V2R2_TARGET_BYTES_REPACKED.zip
""")
    os.chmod(out / "REASSEMBLE_TARGET_EVIDENCE.sh", 0o755)
    index = {
        "core_required_only": True,
        "public_final_commit": PUBLIC_FINAL_COMMIT,
        "optional_current_source": "02_CURRENT_SOURCE_AND_PUBLIC_EVIDENCE.zip",
        "optional_history_reports": "03_HISTORICAL_REPORTS.zip",
        **target_meta,
    }
    write(out / "VOLUME_INDEX.json", json.dumps(index, indent=2, sort_keys=True) + "\n")
    files = [p for p in sorted(out.iterdir()) if p.is_file() and p.name != "ALL_FILES_SHA256.txt"]
    write(out / "ALL_FILES_SHA256.txt", "\n".join(f"{sha256_file(p)}  {p.name}" for p in files) + "\n")
    print(json.dumps({"outputs": [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha256_file(p)} for p in sorted(out.iterdir())]}, indent=2))


if __name__ == "__main__":
    main()
