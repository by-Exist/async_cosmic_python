FROM python:3.10.4 as requirements-stage

RUN pip install poetry
COPY pyproject.toml /tmp/
WORKDIR /tmp
RUN poetry export -f requirements.txt --output /tmp/requirements.txt --without-hashes --dev

FROM python:3.10.4

COPY --from=requirements-stage /tmp/requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip
RUN python -m pip install --no-cache-dir --upgrade -r /tmp/requirements.txt
RUN mkdir -p /src
WORKDIR /src

ENV PYTHONPATH=/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1