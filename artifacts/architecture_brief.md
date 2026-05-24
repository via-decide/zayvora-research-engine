# Architecture Brief

Generated: 2026-05-24T08:44:07.668237+00:00
Research query: Build local-first research-to-architecture pipeline for deterministic engineering outputs

## System Diagram (textual)
```
[Nex Discovery] -> [Zayvora Source Vault] -> [Claim Extractor] -> [Grounding + Confidence]
                     -> [Verification Engine] -> [Architecture Synthesizer] -> [Codex Task Generator]
```

## Grounded Notes
- Stable hashing allows deterministic ids for source and claim nodes. - Hash functions should be consistent across runs to preserve reproducibility. (citation: SRC-001-2d32a1f4:1, confidence: 0.63)
- Grounded responses require explicit citation links. - Contradiction checks reduce hallucination impact in generated summaries. (citation: SRC-003-6f2ff8fd:1, confidence: 0.61)
- Modular chains allow independent verification gates. - Retrieval-augmented pipelines benefit from local caches for latency and auditability. (citation: SRC-002-2f4fb623:1, confidence: 0.44)

## Validation Gates
- Gate 1: All critical claims must contain citation ids.
- Gate 2: Unsupported claims are blocked from architecture decisions.
- Gate 3: Conflicts are manually adjudicated before task emission.

## Implementation Tasks (high-level)
- Implement deterministic parsing and hashing for stable IDs.
- Add reproducible export format for all artifacts.
- Add policy checks for stale/low-quality sources.
