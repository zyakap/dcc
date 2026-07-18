from django.core.management.base import BaseCommand

from api.sync import sync_all_tenants, sync_tenant
from users.models import UserProfile


class Command(BaseCommand):
    help = 'Pull profile/loan/statement feeds from tenant LMS instances into the DCC database.'

    def add_arguments(self, parser):
        parser.add_argument('--luid', help='Sync only the tenant with this LUID (even if feed_enabled is off).')

    def handle(self, *args, **options):
        if options.get('luid'):
            tenant = UserProfile.objects.filter(LUID=options['luid']).first()
            if tenant is None:
                self.stderr.write(self.style.ERROR(f"No tenant with LUID {options['luid']}"))
                return
            results = [sync_tenant(tenant)]
        else:
            results = sync_all_tenants()

        if not results:
            self.stdout.write('No feed-enabled tenants with an API key configured.')
        for r in results:
            style = self.style.SUCCESS if r['ok'] else self.style.ERROR
            self.stdout.write(style(
                f"{r['luid']} ({r['tenant']}): profiles={r['profiles']} loans={r['loans']} "
                f"statements={r['statements']}" + (f" error={r['error']}" if r['error'] else '')
            ))
