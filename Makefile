.PHONY: run stop test seed

run:
	docker compose up --build -d

stop:
	docker compose down

test:
	PYTHONPATH=. pytest -v

seed:
	python scripts/seed.py
