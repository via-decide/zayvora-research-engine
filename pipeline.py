from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


OUTPUT_FILES = [
    "research_query.json",
    "source_manifest.json",
    "claim_graph.json",
    "grounded_summary.md",
    "contradiction_report.json",
    "architecture_brief.md",
    "generated_tasks.md",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SourceRecord:
    source_id: str
    source_type: str
    uri: str
    title: str
    domain: str
    quality_score: float
    stale: bool
    retrieved_at: str
    local_path: str


@dataclass
class Claim:
    claim_id: str
    text: str
    source_id: str
    citation: str
    confidence: float


class SourceFinder:
    def __init__(self, vault_dir: Path) -> None:
        self.vault_dir = vault_dir
        self.sources_dir = vault_dir / "sources"
        self.sources_dir.mkdir(parents=True, exist_ok=True)

    def discover(self, query: dict[str, Any]) -> list[SourceRecord]:
        candidates = query.get("seed_sources") or []
        records: list[SourceRecord] = []
        for i, item in enumerate(candidates, start=1):
            uri = item["uri"]
            parsed = urlparse(uri)
            source_type = self._detect_type(uri)
            title = item.get("title") or Path(parsed.path).name or parsed.netloc
            body = item.get("content") or item.get("summary") or f"Source: {title}\nQuery: {query.get('query','')}"
            source_id = f"SRC-{i:03d}-{hashlib.sha1(uri.encode()).hexdigest()[:8]}"
            local_path = self.sources_dir / f"{source_id}.txt"
            local_path.write_text(body.strip() + "\n", encoding="utf-8")
            quality_score = self._quality_score(parsed.netloc, body)
            records.append(
                SourceRecord(
                    source_id=source_id,
                    source_type=source_type,
                    uri=uri,
                    title=title,
                    domain=parsed.netloc,
                    quality_score=quality_score,
                    stale=False,
                    retrieved_at=now_iso(),
                    local_path=str(local_path.relative_to(self.vault_dir)),
                )
            )
        return records

    @staticmethod
    def _detect_type(uri: str) -> str:
        lower = uri.lower()
        if "github.com" in lower:
            return "github"
        if lower.endswith(".pdf"):
            return "pdf"
        if any(x in lower for x in ["docs.", "/docs", "readthedocs", "developer."]):
            return "docs"
        return "web"

    @staticmethod
    def _quality_score(domain: str, body: str) -> float:
        domain_bonus = 0.2 if domain.endswith((".org", ".edu", ".gov")) else 0.0
        depth_bonus = min(len(body) / 2000, 0.4)
        return round(min(1.0, 0.4 + domain_bonus + depth_bonus), 2)


class GroundingVault:
    claim_pattern = re.compile(r"(?:^|\n)-\s*(.+)")

    def extract_claims(self, sources: list[SourceRecord], vault_dir: Path) -> list[Claim]:
        claims: list[Claim] = []
        for src in sources:
            text = (vault_dir / src.local_path).read_text(encoding="utf-8")
            matches = self.claim_pattern.findall(text)
            if not matches:
                matches = self._fallback_claims(text)
            for idx, c in enumerate(matches, start=1):
                cid = f"CLM-{src.source_id.split('-')[1]}-{idx:02d}"
                confidence = round(min(0.99, src.quality_score * (0.8 + min(len(c), 200) / 1000)), 2)
                claims.append(
                    Claim(
                        claim_id=cid,
                        text=c.strip(),
                        source_id=src.source_id,
                        citation=f"{src.source_id}:{idx}",
                        confidence=confidence,
                    )
                )
        return claims

    @staticmethod
    def _fallback_claims(text: str) -> list[str]:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 30]
        return sentences[:3]


class VerificationEngine:
    def analyze(self, claims: list[Claim], sources: list[SourceRecord]) -> dict[str, Any]:
        source_by_id = {s.source_id: s for s in sources}
        unsupported = [c for c in claims if c.confidence < 0.5]
        conflicts = self._find_conflicts(claims)
        stale_or_low = [
            {
                "source_id": s.source_id,
                "stale": s.stale,
                "quality_score": s.quality_score,
                "reason": "quality below threshold" if s.quality_score < 0.55 else "ok",
            }
            for s in sources
            if s.stale or s.quality_score < 0.55
        ]
        return {
            "generated_at": now_iso(),
            "unsupported_claims": [asdict(c) for c in unsupported],
            "source_conflicts": conflicts,
            "stale_or_low_quality_sources": stale_or_low,
            "claim_coverage": {
                "total_claims": len(claims),
                "supported_claims": len(claims) - len(unsupported),
            },
            "sources_indexed": list(source_by_id.keys()),
        }

    @staticmethod
    def _find_conflicts(claims: list[Claim]) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                a, b = claims[i], claims[j]
                if a.source_id == b.source_id:
                    continue
                if VerificationEngine._is_contradiction(a.text, b.text):
                    conflicts.append(
                        {
                            "claim_a": a.claim_id,
                            "claim_b": b.claim_id,
                            "reason": "opposing polarity on same topic",
                        }
                    )
        return conflicts

    @staticmethod
    def _is_contradiction(a: str, b: str) -> bool:
        tokens_a = set(re.findall(r"[a-zA-Z]+", a.lower()))
        tokens_b = set(re.findall(r"[a-zA-Z]+", b.lower()))
        overlap = len(tokens_a & tokens_b)
        neg_a = any(n in tokens_a for n in {"not", "never", "no", "without"})
        neg_b = any(n in tokens_b for n in {"not", "never", "no", "without"})
        return overlap >= 4 and neg_a != neg_b


class ArchitectureEngine:
    def synthesize(self, query: dict[str, Any], claims: list[Claim]) -> str:
        top_claims = sorted(claims, key=lambda c: c.confidence, reverse=True)[:8]
        lines = [
            "# Architecture Brief",
            "",
            f"Generated: {now_iso()}",
            f"Research query: {query.get('query', '')}",
            "",
            "## System Diagram (textual)",
            "```",
            "[Nex Discovery] -> [Zayvora Source Vault] -> [Claim Extractor] -> [Grounding + Confidence]",
            "                     -> [Verification Engine] -> [Architecture Synthesizer] -> [Codex Task Generator]",
            "```",
            "",
            "## Grounded Notes",
        ]
        for c in top_claims:
            lines.append(f"- {c.text} (citation: {c.citation}, confidence: {c.confidence})")
        lines += [
            "",
            "## Validation Gates",
            "- Gate 1: All critical claims must contain citation ids.",
            "- Gate 2: Unsupported claims are blocked from architecture decisions.",
            "- Gate 3: Conflicts are manually adjudicated before task emission.",
            "",
            "## Implementation Tasks (high-level)",
            "- Implement deterministic parsing and hashing for stable IDs.",
            "- Add reproducible export format for all artifacts.",
            "- Add policy checks for stale/low-quality sources.",
        ]
        return "\n".join(lines) + "\n"


class TaskGenerator:
    def generate(self, claims: list[Claim]) -> str:
        uniq_sources = sorted({c.source_id for c in claims})
        lines = ["# Generated Codex Tasks", ""]
        for idx, source_id in enumerate(uniq_sources, start=1):
            related = [c for c in claims if c.source_id == source_id]
            lines += [
                f"## Task {idx}: Integrate findings from {source_id}",
                "- Determinism: Use stable claim IDs and sorted output order.",
                "- Pass Criteria:",
                "  - [ ] Referenced claims appear in claim_graph.json.",
                "  - [ ] Every architecture note has source citation.",
                "- Source References:",
            ]
            for c in related[:4]:
                lines.append(f"  - {c.claim_id} ({c.citation})")
            lines.append("")
        return "\n".join(lines)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_pipeline(query_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    query = json.loads(query_path.read_text(encoding="utf-8"))
    vault_dir = out_dir / "grounding_vault"

    finder = SourceFinder(vault_dir=vault_dir)
    sources = finder.discover(query)

    gv = GroundingVault()
    claims = gv.extract_claims(sources, vault_dir=vault_dir)

    ve = VerificationEngine()
    report = ve.analyze(claims, sources)

    ae = ArchitectureEngine()
    brief = ae.synthesize(query, claims)

    tg = TaskGenerator()
    tasks = tg.generate(claims)

    write_json(out_dir / "research_query.json", query)
    write_json(out_dir / "source_manifest.json", {"sources": [asdict(s) for s in sources]})
    write_json(out_dir / "claim_graph.json", {"claims": [asdict(c) for c in claims]})
    (out_dir / "grounded_summary.md").write_text(
        "# Grounded Summary\n\n" + "\n".join(f"- {c.text} ({c.citation})" for c in claims) + "\n",
        encoding="utf-8",
    )
    write_json(out_dir / "contradiction_report.json", report)
    (out_dir / "architecture_brief.md").write_text(brief, encoding="utf-8")
    (out_dir / "generated_tasks.md").write_text(tasks, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local-first research-to-architecture pipeline")
    parser.add_argument("--query", type=Path, required=True, help="Path to research_query JSON input")
    parser.add_argument("--out", type=Path, default=Path("artifacts"), help="Output directory")
    args = parser.parse_args()
    run_pipeline(args.query, args.out)


if __name__ == "__main__":
    main()
