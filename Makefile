.PHONY: build up down test logs clean

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

test:
	pytest

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -r {} +
