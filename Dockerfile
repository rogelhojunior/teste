FROM ubuntu:22.04 as build-image

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APPLICATIONDIR=/core

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-dev \
    python3-venv \
    python3-pip \
    python3-enchant \
    build-essential \
    default-libmysqlclient-dev \
    libenchant-2-dev && \
    rm -fr /var/lib/apt/lists && \
    apt-get clean && \
    apt-get autoremove && \
    apt-get autoclean -y

RUN text -d ${APPLICATIONDIR} || mkdir -p ${APPLICATIONDIR}

ENV VIRTUAL_ENV=${APPLICATIONDIR}/venv
RUN python3 -m venv ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

COPY requirements.txt .
RUN pip3 config set global.trusted-host=pypi.org files.pythonhosted.org
RUN pip3 install -U pip
RUN pip3 install --no-cache-dir wheel
RUN pip3 install --no-cache-dir -r requirements.txt

# Build runner image
FROM ubuntu:22.04 as runner-image

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LOCALE=pt_BR.UTF-8
ENV LANG=${LOCALE}
ENV LANGUAGE=${LOCALE}
ENV LC_CTYPE=${LOCALE}
ENV LC_NUMERIC=${LOCALE}
ENV LC_TIME=${LOCALE}
ENV LC_COLLATE=${LOCALE}
ENV LC_MONETARY=${LOCALE}
ENV LC_MESSAGES=${LOCALE}
ENV LC_PAPER=${LOCALE}
ENV LC_NAME=${LOCALE}
ENV LC_ADDRESS=${LOCALE}
ENV LC_TELEPHONE=${LOCALE}
ENV LC_MEASUREMENT=${LOCALE}
ENV LC_IDENTIFICATION=${LOCALE}
ENV LC_ALL=C
ENV GUNICORNADDRESS=0.0.0.0
ENV GUNICORNPORT=8000
ENV CNAME=core
ENV APPLICATIONDIR=/core
ENV NEW_RELIC_CONFIG_FILE=${APPLICATIONDIR}/newrelic.ini

ENV SSL_CERT_DIR=/etc/ssl/certs

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    python3-distutils \
    default-libmysqlclient-dev \
    libenchant-2-dev \
    libnginx-mod-nchan \
    locales \
    nginx \
    poppler-utils && \
    update-ca-certificates --fresh && \
    rm -fr /var/lib/apt/lists && \
    apt-get clean && \
    apt-get autoremove && \
    apt-get autoclean -y

RUN text -d ${APPLICATIONDIR} || mkdir -p ${APPLICATIONDIR}
WORKDIR ${APPLICATIONDIR}

# FIX LOCALE
RUN sed -i -e 's/# pt_BR.UTF-8 UTF-8/pt_BR.UTF-8 UTF-8/' /etc/locale.gen && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=${LOCALE}

# NGINX
COPY nginx.conf /etc/nginx/sites-available/default

ENV VIRTUAL_ENV=${APPLICATIONDIR}/venv
COPY --from=build-image ${VIRTUAL_ENV} ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

COPY . ${APPLICATIONDIR}

EXPOSE 80
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
