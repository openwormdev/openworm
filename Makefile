PYTHON ?= python3

.PHONY: test build doctor serve recordings
test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	npm test
	npm run check
build:
	npm run build
doctor:
	PYTHONPATH=src $(PYTHON) -m wormstreet.cli doctor
serve:
	PYTHONPATH=src $(PYTHON) -m wormstreet.cli serve
recordings:
	PYTHONPATH=src $(PYTHON) -m wormstreet.cli replay --scenario reversal --output web/data/reversal.json
	PYTHONPATH=src $(PYTHON) -m wormstreet.cli replay --scenario trend --output web/data/trend.json
	PYTHONPATH=src $(PYTHON) -m wormstreet.cli replay --scenario liquidity-shock --output web/data/liquidity-shock.json
	node scripts/recordings.mjs
