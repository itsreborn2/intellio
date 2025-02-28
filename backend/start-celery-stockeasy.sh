#!/bin/bash
celery -A stockeasy.core.celery_app beat --loglevel=INFO &
celery -A stockeasy.core.celery_app worker -n stockeasy@%h --loglevel=INFO -Q telegram-processing,embedding-processing --pool=threads --concurrency=${CELERY_CONCURRENCY_STOCKEASY:-1} --events 