# Research-record targets. See docs/research/AGENT_INSTRUCTIONS.md.
#
# This Makefile exists for the research record only — it is not the project's
# build system. Application commands stay on `uv run main.py` / `app.py`; see
# docs/commands.md for the full reference.

.PHONY: help new-experiment validate-research index figures test-research

UV ?= uv

help:
	@echo "Research record targets:"
	@echo "  make new-experiment SLUG=<slug>  Scaffold an experiment folder"
	@echo "  make validate-research           Validate every experiment (section 7.3)"
	@echo "  make index                       Regenerate docs/research/INDEX.md"
	@echo "  make figures                     Regenerate every promoted figure"
	@echo "  make test-research               Run the research-record test suite"

new-experiment:
ifndef SLUG
	$(error SLUG is required: make new-experiment SLUG=my-experiment)
endif
	@$(UV) run python scripts/new_experiment.py $(SLUG)

validate-research:
	@$(UV) run python scripts/validate_research.py

index:
	@$(UV) run python scripts/generate_index.py

figures:
	@$(UV) run python scripts/make_figures.py

test-research:
	@$(UV) run pytest utils/research_record/tests -q
