from django.core.management.base import BaseCommand

from loan.models import Loan
from client.models import ClientProfile


class Command(BaseCommand):
    help = 'Backfill Loan.owner for loans that have UID/LUID but no owner FK set.'

    def handle(self, *args, **options):
        loans = Loan.objects.filter(owner__isnull=True, UID__isnull=False, LUID__isnull=False)
        total = loans.count()
        self.stdout.write(f'{total} loan(s) missing an owner — attempting backfill...')

        fixed = 0
        unresolved = 0
        for loan in loans.iterator():
            client = ClientProfile.objects.filter(LUID=loan.LUID, CUID=loan.UID).first()
            if client:
                loan.owner = client
                loan.save(update_fields=['owner'])
                fixed += 1
            else:
                unresolved += 1
                self.stdout.write(self.style.WARNING(
                    f'  No client found for loan {loan.ref} (LUID={loan.LUID}, UID={loan.UID})'
                ))

        self.stdout.write(self.style.SUCCESS(f'Done: {fixed} fixed, {unresolved} unresolved.'))
        if unresolved:
            self.stdout.write(
                'Unresolved loans have no matching ClientProfile yet — '
                'run sync_tenants first, then re-run this command.'
            )
