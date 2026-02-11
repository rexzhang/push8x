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
	python -m push8x -c $CONFIG_FILENAME serve
