.PHONY: build test lint

build:
	@python3 -m compileall -q src

test:
	@python3 -m unittest discover -s tests -t .

lint:
	@python3 -W error -m compileall -q src tests
