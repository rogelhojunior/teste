#!/bin/bash
if [[ $CNAME == 'celery' ]]
then
    echo 'Start workers'
    celery -A core worker -n reports -c 4 -P gevent -l info -Q reports --detach
    celery -A core worker -n recalculation -c 4 -P gevent -l info -Q recalculation --detach
    celery -A core worker -n light_operations -c 8 -P gevent -l info -Q light_operations --detach
    celery -A core worker -n heavy_operations -c 4 -P gevent -l info -Q heavy_operations --detach

    echo 'Start Application - Celery'
    newrelic-admin run-program \
        celery \
        -A core worker \
        -P gevent \
        -c 8 \
        -n %h-01 \
        -l info \
        -Q celery

elif [[ $CNAME == 'flower' ]]
then
    echo 'Start Application - Celery and Flower'
    newrelic-admin run-program celery -A core --broker=$CELERY_BROKER_URL flower --basic-auth=$FLOWER_BASIC_AUTH --port=80
elif [[ $CNAME == 'celery-beat' ]]
then
    echo 'Start Application - Celery Beat'
    newrelic-admin run-program \
        celery \
        -A core beat \
        --scheduler django_celery_beat.schedulers:DatabaseScheduler \
        -l info
elif [[ $CNAME == 'tasks' ]]
then
    echo 'Start Task' $TASK_NAME
    python manage.py $TASK_NAME
    echo 'Stop Task' $TASK_NAME
else
    echo 'Start NGINX'
    service nginx start

    echo '------------------'

    echo 'Start Migrate'
    python manage.py migrate
    if [[ $ENVIRONMENT == 'PROD' ]]
    then
        python manage.py migrate --database=audit
    fi
    echo '------------------'

    echo 'Start Collectstatic'
    python manage.py collectstatic
    echo '------------------'

    echo 'Start Application - Core'
    newrelic-admin run-program \
        gunicorn core.wsgi:application \
            --bind ${GUNICORNADDRESS}:${GUNICORNPORT} \
            --workers 2 \
            --threads 4 \
            --timeout 120 \
            --log-level info

fi
