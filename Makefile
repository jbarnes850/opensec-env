.PHONY: install install-dev install-training test test-all lint server docker-server docker-training train-dry-run train train-curriculum baseline-eval clean

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

install-training:
	pip install -e ".[training]"

test:
	pytest tests/ -v --ignore=tests/test_server_smoke.py

test-all:
	pytest tests/ -v

lint:
	python -m py_compile scripts/train_gdpo.py
	python -m py_compile scripts/run_oracle_baseline.py
	python -c "from training import *; print('Training module OK')"

server:
	uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload

docker-server:
	docker build -t opensec-env:latest .
	docker run -p 8000:8000 opensec-env:latest

docker-training:
	docker build -f Dockerfile.training -t opensec-env-training:latest .

train-dry-run:
	python scripts/train_gdpo.py --dry-run --model Qwen/Qwen3-0.6B

train:
	python scripts/train_gdpo.py --config configs/gdpo_1.7b.yaml

train-curriculum:
	python scripts/train_gdpo.py --curriculum --use-eval-curriculum

baseline-eval:
	python scripts/run_llm_baseline.py --tier trivial --limit 1

clean:
	rm -rf outputs/gdpo outputs/rl data/sqlite/*.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
