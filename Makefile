# Root convenience wrapper. The real targets live in backend/Makefile so they can
# be run from either directory: `make <target>` here, or `make <target>` inside
# backend/.
.DEFAULT_GOAL := help

BACKEND := backend

.PHONY: help

help: ## Show available targets
	@$(MAKE) --no-print-directory -C $(BACKEND) help

# Forward every other target to backend/ (install, dev, start, stop, ...).
%:
	@$(MAKE) --no-print-directory -C $(BACKEND) $@