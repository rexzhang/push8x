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
	python -m push8x -c $CONFIG_FILENAME serve --http-bind-host $HTTP_BIND_HOST --http-bind-port $HTTP_BIND_PORT --smtpd-bind-host $SMTPD_BIND_HOST --smtpd-bind-port $SMTPD_BIND_PORT
