from celery import shared_task

from .sync import sync_all_tenants


@shared_task
def sync_tenant_feeds():
    """Scheduled pull of every feed-enabled tenant's LMS data into DCC."""
    results = sync_all_tenants()
    return results
