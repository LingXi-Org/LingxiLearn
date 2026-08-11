"""Load and validate course packs from YAML.

Validation returns stable issue codes rather than prose, so tests assert on
behaviour and the messages stay freely editable and translatable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..tools.registry import ToolRegistry
from .models import (
    Artifact,
    Concept,
    Item,
    Misconception,
    Mission,
    Pack,
    Step,
    ToolCall,
    ValidationIssue,
    ValidationResult,
)


class PackError(RuntimeError):
    pass


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PackError(f"missing pack file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PackError(f"{path} must contain a YAML mapping")
    return data


def _items(raw: list[dict[str, Any]] | None) -> list[Item]:
    return [
        Item(
            id=str(entry["id"]),
            concept=str(entry.get("concept", "")),
            prompt=str(entry.get("prompt", "")),
            expects=str(entry.get("expects", "choice")),
            choices=list(entry.get("choices", [])),
            grader=dict(entry.get("grader", {})),
            explain=str(entry.get("explain", "")),
            difficulty=int(entry.get("difficulty", 1)),
        )
        for entry in (raw or [])
    ]


def _steps(raw: list[dict[str, Any]] | None) -> list[Step]:
    steps: list[Step] = []
    for entry in raw or []:
        tools = [
            ToolCall(
                call=str(t["call"]),
                args=dict(t.get("args", {})),
                as_=str(t.get("as", "")),
                summary=str(t.get("summary", "")),
            )
            for t in entry.get("tools", [])
        ]
        steps.append(
            Step(
                id=str(entry["id"]),
                title=str(entry.get("title", "")),
                objective=str(entry.get("objective", "")),
                concepts=[str(c) for c in entry.get("concepts", [])],
                scene=str(entry.get("scene", "packet_lab")),
                ask=str(entry.get("ask", "")),
                expects=str(entry.get("expects", "text")),
                choices=list(entry.get("choices", [])),
                tools=tools,
                grader=dict(entry.get("grader", {})),
                hint_ladder=[str(h) for h in entry.get("hint_ladder", [])],
                walkthrough=str(entry.get("walkthrough", "")),
                leak_guard=dict(entry.get("leak_guard", {})),
                reveal_after=int(entry.get("reveal_after", 3)),
                max_attempts=int(entry.get("max_attempts", 4)),
                stage_props=dict(entry.get("stage_props", {})),
                knowledge=[str(k) for k in entry.get("knowledge", [])],
                skip_if_mastered=float(entry.get("skip_if_mastered", 0.0)),
            )
        )
    return steps


def load_pack(root: Path) -> Pack:
    root = Path(root)
    manifest = _read_yaml(root / "pack.yaml")

    concept_data = _read_yaml(root / manifest.get("concepts_file", "concepts.yaml"))
    concepts = {
        str(c["id"]): Concept(
            id=str(c["id"]),
            title=str(c.get("title", c["id"])),
            requires=[str(r) for r in c.get("requires", [])],
            summary=str(c.get("summary", "")),
        )
        for c in concept_data.get("concepts", [])
    }
    misconceptions = {
        str(m["id"]): Misconception(
            id=str(m["id"]),
            title=str(m.get("title", m["id"])),
            concept=str(m.get("concept", "")),
            note=str(m.get("note", "")),
        )
        for m in concept_data.get("misconceptions", [])
    }

    missions: dict[str, Mission] = {}
    for mission_id in manifest.get("missions", []):
        mdir = root / "missions" / str(mission_id)
        mdata = _read_yaml(mdir / "mission.yaml")
        artifacts = {
            str(a["id"]): Artifact(
                id=str(a["id"]),
                kind=str(a.get("kind", "file")),
                path=(mdir / str(a["path"])).resolve(),
                title=str(a.get("title", "")),
                source=str(a.get("source", "synthetic")),
                license=str(a.get("license", "CC0-1.0")),
            )
            for a in mdata.get("artifacts", [])
        }
        missions[str(mission_id)] = Mission(
            id=str(mission_id),
            title=str(mdata.get("title", mission_id)),
            subtitle=str(mdata.get("subtitle", "")),
            summary=str(mdata.get("summary", "")),
            concepts=[str(c) for c in mdata.get("concepts", [])],
            steps=_steps(mdata.get("steps")),
            probe=_items(mdata.get("probe")),
            verify=_items(mdata.get("verify")),
            artifacts=artifacts,
            why_not_chat=str(mdata.get("why_not_chat", "")),
            estimated_minutes=int(mdata.get("estimated_minutes", 15)),
        )

    return Pack(
        id=str(manifest["id"]),
        title=str(manifest.get("title", manifest["id"])),
        version=str(manifest.get("version", "0.0.0")),
        description=str(manifest.get("description", "")),
        root=root,
        concepts=concepts,
        misconceptions=misconceptions,
        missions=missions,
    )


def discover_packs(packs_dir: Path) -> dict[str, Pack]:
    packs: dict[str, Pack] = {}
    if not packs_dir.exists():
        return packs
    for child in sorted(packs_dir.iterdir()):
        if (child / "pack.yaml").exists():
            pack = load_pack(child)
            packs[pack.id] = pack
    return packs


def validate_pack(pack: Pack, registry: ToolRegistry | None = None) -> ValidationResult:
    """Structural checks that catch authoring mistakes before a learner does."""
    issues: list[ValidationIssue] = []

    def add(path: str, code: str, message: str) -> None:
        issues.append(ValidationIssue(path=path, code=code, message=message))

    for cid, concept in pack.concepts.items():
        for req in concept.requires:
            if req not in pack.concepts:
                add(f"concepts.{cid}.requires", "unknown_prerequisite", f"未知前置概念 {req}")

    for mid, misc in pack.misconceptions.items():
        if misc.concept and misc.concept not in pack.concepts:
            add(f"misconceptions.{mid}.concept", "unknown_concept", f"未知概念 {misc.concept}")
        if not misc.note:
            add(f"misconceptions.{mid}.note", "missing_note", "缺少针对性追问文案")

    if not pack.missions:
        add("missions", "no_missions", "课程包没有任何任务")

    for mission in pack.missions.values():
        base = f"missions.{mission.id}"
        if not mission.steps:
            add(f"{base}.steps", "no_steps", "任务没有教学步骤")
        if not mission.probe:
            add(f"{base}.probe", "no_probe", "任务缺少前测，无法度量学习增益")
        if not mission.verify:
            add(f"{base}.verify", "no_verify", "任务缺少后测，无法验证是否真的学会")

        for concept in mission.concepts:
            if concept not in pack.concepts:
                add(f"{base}.concepts", "unknown_concept", f"未知概念 {concept}")

        seen_steps: set[str] = set()
        for step in mission.steps:
            spath = f"{base}.steps.{step.id}"
            if step.id in seen_steps:
                add(spath, "duplicate_step", f"步骤 id 重复：{step.id}")
            seen_steps.add(step.id)

            if not step.ask:
                add(spath, "missing_ask", "步骤没有给学生的问题")
            if not step.hint_ladder:
                add(spath, "missing_hint_ladder", "步骤缺少提示阶梯，无法在不泄题的情况下引导")
            if not step.grader.get("kind"):
                add(spath, "missing_grader", "步骤没有判定方式")
            if not step.walkthrough:
                add(spath, "missing_walkthrough", "步骤缺少复盘讲解")
            if not step.leak_guard.get("phrases") and not step.leak_guard.get("numbers"):
                add(spath, "missing_leak_guard", "步骤没有声明答案标记，无法度量泄题")

            for concept in step.concepts:
                if concept not in pack.concepts:
                    add(spath, "unknown_concept", f"未知概念 {concept}")

            for call in step.tools:
                if registry is not None and call.call not in registry.specs:
                    add(f"{spath}.tools", "unknown_tool", f"未注册的工具 {call.call}")
                artifact = call.args.get("artifact")
                if isinstance(artifact, str) and artifact not in mission.artifacts:
                    add(f"{spath}.tools", "unknown_artifact", f"未声明的工件 {artifact}")

        for bucket, items in (("probe", mission.probe), ("verify", mission.verify)):
            for item in items:
                ipath = f"{base}.{bucket}.{item.id}"
                if item.concept not in pack.concepts:
                    add(ipath, "unknown_concept", f"未知概念 {item.concept}")
                if not item.grader.get("kind"):
                    add(ipath, "missing_grader", "题目没有判定方式")

        for artifact in mission.artifacts.values():
            if not artifact.path.exists():
                add(
                    f"{base}.artifacts.{artifact.id}",
                    "missing_artifact",
                    f"工件文件不存在：{artifact.path}（先运行 scripts/build_artifacts.py）",
                )

    return ValidationResult(valid=not issues, issues=issues)
