FROM python:3.10.4

RUN python -m pip install --upgrade pip

COPY requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt

RUN mkdir -p /src

WORKDIR /src

ENV PYTHONPATH=/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1