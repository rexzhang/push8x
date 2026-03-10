#!/bin/sh

echo "
------------------
App user's UID:GID

$UID:$GID
------------------
"

echo "prepare..."
chown -R $UID:$GID /data

echo "server starting..."
exec su-exec $UID:$GID \
	python -m push8x -c $CONFIG_FILENAME serve --http-listen-host $HTTP_LISTEN_HOST --http-listen-port $HTTP_LISTEN_PORT --smtpd-listen-host $SMTPD_LISTEN_HOST --smtpd-listen-port $SMTPD_LISTEN_PORT
