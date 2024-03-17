def get_default_task_args(
    queue='celery',
    auto_retry_for=(Exception,),
    max_retries=5,
    retry_backoff=1800,
    retry_jitter=True,
) -> dict:
    """
    Returns default task behavior
    Args:
        queue: celery queue (needs to be declared in celery.py file)

    Returns:
        dict: with task options
    """
    return {
        'queue': queue,
        'autoretry_for': auto_retry_for,
        'max_retries': max_retries,
        'retry_backoff': retry_backoff,
        'retry_jitter': retry_jitter,
    }
