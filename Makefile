.PHONY: run stop test seed

run:
	docker compose up --build -d

stop:
	docker compose down

test:
	PYTHONPATH=. venv/bin/python -m pytest -v

seed:
	venv/bin/python scripts/seed.py
