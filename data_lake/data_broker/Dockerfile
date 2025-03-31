FROM python:3.8.6-slim-buster
ENV PYTHONUNBUFFERED=1

# Basic requirements needed to build msodbcsql17 and python modules
# RUN apt-get update
# libgssapi-krb5-2 is required by msodbcsql17, but not marked as a dependency;
# we install it explicitly to prevent autoremoval below
# RUN apt-get install -y gnupg curl gcc g++ unixodbc unixodbc-dev libgssapi-krb5-2 nginx

# ODBC driver needed to connect to azure
# RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
# RUN curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list
RUN apt-get update
# RUN ACCEPT_EULA=Y apt-get install -y msodbcsql17

WORKDIR /broker

# Copy requirements separately, so changes to other files do not trigger a re-build
COPY ./container/requirements/*.txt requirements/
RUN pip install --no-cache-dir -r requirements/production.txt

# Management of Lets Encrypt SSL/HTTPS certificates
RUN apt-get install -y certbot python-certbot-nginx cron

# Allow final size to be reduced with 'docker build --squash [...]'
# RUN apt-get autoremove --purge -y gnupg curl gcc g++ unixodbc-dev
RUN rm -rf /var/cache/apt/

# Copy default nginx config, for testing/certbot setup
COPY ./container/nginx.conf /etc/nginx/

# Copy everything (else)
COPY ./container/ .

EXPOSE 443

CMD ["bash", "./start.sh"]