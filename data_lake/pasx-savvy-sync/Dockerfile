FROM python:3.8.1-slim-buster
ENV PYTHONUNBUFFERED=1

WORKDIR /container

# Copy requirements separately, so changes to other files do not trigger a re-build
COPY ./container/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything (else)
COPY ./container/ .
COPY ./config.ini .

RUN python3 setup.py install

ENTRYPOINT ["pasx_savvy_sync", "--config", "config.ini"]