#!/bin/sh
# Render's start command (render.yaml dockerCommand). A file instead of
# an inline command because Render tokenizes dockerCommand rather than
# handing the string to a shell: `a && b` arrives as literal arguments,
# a quoted command arrives with its quotes attached, and either way the
# process that starts is not the one intended — the deploy died with
# `sh: 1: <the entire command>: not found` twice before this file
# existed. A single path tokenizes to itself under every parser.
#
# Migration-then-serve, unlike compose's one-shot `migrate` service: a
# free instance is exactly one replica, so the two-replicas-both-running
# `upgrade head` race that justifies the separate service cannot occur,
# and Render's pre-deploy command is a paid feature. Move the upgrade to
# `preDeployCommand` before ever scaling past one instance.
set -e
alembic upgrade head
exec uvicorn planbench_api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
