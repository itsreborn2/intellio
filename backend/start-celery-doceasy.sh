#!/bin/bash

celery -A doceasy.core.celery_app worker \
    -n doceasy@%h \
    --loglevel=INFO \
    -Q document-processing,main-queue,rag-processing \
    --pool=threads \
    --concurrency="${CELERY_CONCURRENCY_DOCEASY:-1}" \
    --events 