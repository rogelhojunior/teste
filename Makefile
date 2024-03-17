PROJECT_NAME := originacao-backend
PYTHON_VERSION := 3.10.4
VENV_NAME := $(PROJECT_NAME)-$(PYTHON_VERSION)
PATH_TO_REQUIREMENTS := ""

.create-venv:
	CC=clang pyenv install -s $(PYTHON_VERSION)
	pyenv uninstall -f $(VENV_NAME)
	pyenv virtualenv $(PYTHON_VERSION) $(VENV_NAME)
	pyenv local $(VENV_NAME)
	pip install pip -U

setup:
	pip install -r $(PATH_TO_REQUIREMENTS)requirements.txt

create-venv: .create-venv setup

up:
	docker-compose up -d

up-build:
	docker-compose up --build -d

build:
	docker-compose build

down:
	docker-compose down --remove-orphans

up-only-dbs:
	docker-compose up redis mysql -d

shell_plus:
	python manage.py shell_plus

local-migrate:
	python manage.py migrate

local-makemigrations:
	python manage.py makemigrations
