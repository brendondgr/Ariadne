# Research-record targets. See docs/research/AGENT_INSTRUCTIONS.md.
#
# This Makefile exists for the research record only — it is not the project's
# build system. Application commands stay on `uv run main.py` / `app.py`; see
# docs/commands.md for the full reference.

.PHONY: help new-experiment validate-research index figures test-research verify-paper-numbers check-docs check-record

UV ?= uv

help:
	@echo "Research record targets:"
	@echo "  make new-experiment SLUG=<slug>  Scaffold an experiment folder"
	@echo "  make validate-research           Validate every experiment (section 7.3)"
	@echo "  make index                       Regenerate docs/research/INDEX.md"
	@echo "  make figures                     Regenerate every promoted figure"
	@echo "  make test-research               Run the research-record test suite"
	@echo "  make verify-paper-numbers        Review list: every number in the paper, traced or not"
	@echo "  make check-docs                  GATE: no prose document quotes a withdrawn or superseded figure"
	@echo "  make check-record                Everything the pre-commit hook runs, over the whole record"

new-experiment:
ifndef SLUG
	$(error SLUG is required: make new-experiment SLUG=my-experiment)
endif
	@$(UV) run python scripts/new_experiment.py $(SLUG)

validate-research:
	@$(UV) run python scripts/validate_research.py

index:  ## regenerate INDEX.md and CURRENT.md from the manifests
	@$(UV) run python scripts/generate_index.py

figures:
	@$(UV) run python scripts/make_figures.py

test-research:
	@$(UV) run pytest utils/research_record/tests -q

verify-paper-numbers:  ## review list: every number in the paper, traced / untraced / stale
	@$(UV) run python scripts/verify_paper_numbers.py

check-docs:  ## gate: README, ledgers, paper and docs quote no withdrawn or superseded figure
	@$(UV) run python scripts/verify_paper_numbers.py --docs --gate --quiet

check-record: validate-research check-docs  ## the full gate: validator + index freshness + stale-quote scan
	@$(UV) run python scripts/generate_index.py --check
	@$(UV) run pytest utils/research_record/tests utils/specialists/tests/test_docs_contracts.py -q
