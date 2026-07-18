from django.core.management.base import BaseCommand

from api.tasks import recompute_credit_scores
from client.models import ClientCreditScore, ClientProfile, matched_profiles


class Command(BaseCommand):
    help = 'Recompute the DCC benchmark credit score for every client (or one CUID).'

    def add_arguments(self, parser):
        parser.add_argument('--cuid', help='Recompute only the person matching this client CUID.')

    def handle(self, *args, **options):
        if options.get('cuid'):
            seed = ClientProfile.objects.filter(CUID=options['cuid'])
            profiles = matched_profiles(seed)
            if not profiles:
                self.stderr.write(self.style.ERROR(f"No client with CUID {options['cuid']}"))
                return
            primary = sorted(profiles, key=lambda p: p.updated_at or p.created_at, reverse=True)[0]
            score = ClientCreditScore.ensure(primary, profiles=profiles)
            self.stdout.write(self.style.SUCCESS(
                f'{primary}: {score.score}/1000 ({score.grade}) across {len(profiles)} profile(s)'))
            return

        result = recompute_credit_scores()
        self.stdout.write(self.style.SUCCESS(
            f"Scored {result['persons_scored']} person(s) covering {result['profiles_covered']} profile(s)."))
