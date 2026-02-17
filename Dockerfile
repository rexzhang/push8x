FROM python:3.12-alpine

ARG BUILD_ENV
ARG IMAGE_VERSION

ENV TZ="Asia/Shanghai"
ENV UID=1000
ENV GID=1000
ENV HTTP_BIND_HOST="0.0.0.0"
ENV HTTP_BIND_PORT="8000"
ENV SMTPD_BIND_HOST="0.0.0.0"
ENV SMTPD_BIND_PORT="8025"
ENV CONFIG_FILENAME="/etc/push8x.toml"

RUN if [ "$BUILD_ENV" = "rex" ]; then echo "Change depends" \
    && pip config set global.index-url https://proxpi.h.rexzhang.com/index/ \
    && pip config set install.trusted-host proxpi.h.rexzhang.com \
    && sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories \
    ; fi

COPY requirements.d /app/requirements.d

RUN \
    # install python build depends ---
    apk add --no-cache --virtual .build-deps build-base libffi-dev \
    # --- build & install
    && pip install --no-cache-dir -r /app/requirements.d/docker.txt \
    # --- cleanup
    && apk del .build-deps \
    && rm -rf /root/.cache \
    && find /usr/local/lib/python*/ -type f -name '*.py[cod]' -delete \
    && find /usr/local/lib/python*/ -type d -name "__pycache__" -delete \
    # create non-root user ---
    && apk add --no-cache su-exec \
    # support timezone ---
    && apk add --no-cache tzdata \
    # prepare ---
    && mkdir /data

COPY push8x /app/push8x
COPY entrypoint.sh /app/entrypoint.sh

WORKDIR /app
VOLUME /data
EXPOSE 8000 8025

CMD [ "/app/entrypoint.sh" ]

LABEL org.opencontainers.image.title="Push Router"
LABEL org.opencontainers.image.version="$IMAGE_VERSION"
LABEL org.opencontainers.image.authors="Rex Zhang"
LABEL org.opencontainers.image.source="https://github.com/rexzhang/push8x"
