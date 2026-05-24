# zayvora-research-engine

Local-first **research-to-architecture pipeline** implementation.

## What this provides

The pipeline processes a research query through these deterministic stages:

1. Nex source discovery (`SourceFinder`)
2. Zayvora source vault storage (`grounding_vault/sources/*`)
3. Claim extraction (`GroundingVault`)
4. Citation-grounded summary (`grounded_summary.md`)
5. Contradiction + unsupported-claim detection (`VerificationEngine`)
6. Architecture synthesis (`ArchitectureEngine`)
7. Codex task generation (`TaskGenerator`)

## Run

```bash
python3 pipeline.py --query sample_query.json --out artifacts
```

## Produced artifacts

- `research_query.json`
- `source_manifest.json`
- `claim_graph.json`
- `grounded_summary.md`
- `contradiction_report.json`
- `architecture_brief.md`
- `generated_tasks.md`

## Pass criteria mapping

- ✅ sources stored locally (`artifacts/grounding_vault/sources/*`)
- ✅ every major claim links to source (`claim_graph.json` + `grounded_summary.md`)
- ✅ unsupported claims flagged (`contradiction_report.json`)
- ✅ contradictions detected (`contradiction_report.json`)
- ✅ architecture brief generated (`architecture_brief.md`)
- ✅ Codex tasks generated (`generated_tasks.md`)
