# Agentic SDD Research Notes

更新日: 2026-06-07

## 1. 調査対象

| 対象 | 参照 | 観測 |
| ---- | ---- | ---- |
| GitHub Spec Kit | https://github.github.com/spec-kit/index.html | SDD を AI-assisted development の中心に置き、`Spec -> Plan -> Tasks -> Implement` を中核にする。 |
| Spec Kit Quick Start | https://github.github.com/spec-kit/quickstart.html | production feature では clarify、checklist、analyze を quality gate として使う。 |
| Spec Kit SDD Concept | https://github.github.com/spec-kit/concepts/sdd.html | 仕様を what の source of truth とし、one-shot prompt ではなく multi-step refinement を重視する。 |
| Kiro Feature Specs | https://kiro.dev/docs/specs/feature-specs/ | requirements、design、tasks を分け、requirements-first と design-first を選べる。 |
| Kiro Specs | https://kiro.dev/docs/specs/ | task dependency graph を wave として実行し、独立 task を並列化する。 |
| Claude Code Best Practices | https://code.claude.com/docs/en/best-practices | Agent に検証可能な check を与え、explore、plan、code、verify の loop を作る。 |
| OpenAI Codex Subagents | https://developers.openai.com/codex/subagents | Subagent は明示依頼時に起動し、並列 exploration や multi-step feature plan に有効。Agentic SDD 開始指示を project-local な包括許可として扱えば、Main Agent に orchestration を委譲できる。 |
| OpenAI Codex Hooks | https://developers.openai.com/codex/hooks | project-local hooks は trusted `.codex` layer で有効になり、tool 実行前後の guardrail に使える。 |
| OpenAI Codex Non-interactive | https://developers.openai.com/codex/noninteractive | `codex exec` は CI や structured output に使えるが、初期運用ではローカル中心に留める。 |

## 2. 採用する考え方

| 外部手法 | 採用判断 | ponkan-python での形 |
| -------- | -------- | -------------------- |
| Spec -> Plan -> Tasks -> Implement | 採用 | `spec/initial` と作業仕様を source of truth にする |
| Clarify / Checklist / Analyze | 軽量採用 | requirements gate、plan gate、task consistency gate として扱う |
| Requirements-first / Design-first | 採用 | product behavior は requirements-first、USB/protocol は design-first を許可する |
| Task dependency graph | 採用 | Subagent 分担前に blocking / sidecar / hardware task を分類する |
| Parallel task waves | 採用 | sidecar task を必要に応じて並列化する。並列実装は変更範囲と統合リスクを確認して扱う |
| Verification-first agentic coding | 採用 | `uv run pytest`、ruff、ty、source audit、hardware gate を stop condition にする |
| Adversarial review | 部分採用 | Subagent review は gate 補助であり主役にしない |
| Non-interactive automation | 後段採用 | CI/PR 自動化は local workflow が安定してから検討する |

## 3. 採用しない考え方

| 対象 | 採用しない理由 |
| ---- | -------------- |
| 外部 Spec Kit の導入 | 既に project-local spec / skill / hook があり、現段階では過剰。 |
| 毎回の厚いドメイン説明 | `spec/initial` が目的、scope、非対象、安全制約を満たしている。 |
| 変更範囲が広い並列実装 | 小規模 repo かつ protocol safety が重要なため、初期は統合リスクが高い。 |
| review 中心 workflow | 根幹は自律実装であり、review は品質ゲートに留める。 |

## 4. この repo への結論

`ponkan-python` では、ユーザが毎回ドメイン背景を説明し直すのではなく、`spec/initial` を Constitution として扱う。ユーザは Intent Delta と Risk Approval を担当し、Main Agent は Work Unit 選択、Plan、Task Graph、TDD 実装、Gate 報告を担当する。

Subagent は採用する。Agentic SDD workflow が開始されたら、Main Agent は sidecar task を必要に応じて自動起動する。原典調査、テスト品質、実機安全、統合リスクなどの gate を並列化し、workflow が安定した後に並列実装の扱いを検討する。
