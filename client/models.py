from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.forms import DecimalField, FileField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django.db import models
from users.models import UserProfile


class _AuditedModel(models.Model):
    """Abstract mixin: on every save(), diffs this instance's tracked fields
    against what is currently in the database and appends any change to
    ClientProfileHistory — the single audit trail for everything DCC knows
    about a client, across every tenant that has ever fed data about them.

    This is deliberately a database-diff on save(), not a signal on the
    incoming tenant feed, so it also captures direct edits made by DCC staff
    (e.g. via /appadmin/), not just tenant-sync writes. The very first save()
    of a row is logged too (old_value=None), so "the first copy" of a fact is
    preserved exactly like every value after it — nothing is only ever
    overwritten in place.
    """
    _history_excluded_fields = ('id', 'created_at', 'updated_at')
    _history_prefix = ''

    class Meta:
        abstract = True

    def _history_client(self):
        """The ClientProfile this instance's history rows belong to."""
        if isinstance(self, ClientProfile):
            return self
        return getattr(self, 'client', None)

    def save(self, *args, _history_source='MANUAL', **kwargs):
        old = None
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
        super().save(*args, **kwargs)
        self._record_history(old, source=_history_source)

    def _record_history(self, old, source='MANUAL'):
        client = self._history_client()
        if client is None or client.pk is None:
            return
        entries = []
        for f in self._meta.fields:
            name = f.name
            if name in self._history_excluded_fields:
                continue
            new_val = getattr(self, name)
            old_val = getattr(old, name) if old is not None else None
            new_str = '' if new_val in (None, '') else str(new_val)
            old_str = '' if old_val in (None, '') else str(old_val)
            if new_str == old_str:
                continue
            if old is None and not new_str:
                continue  # nothing worth recording on creation if left blank
            entries.append(ClientProfileHistory(
                client=client,
                field_name=f'{self._history_prefix}{name}',
                old_value=old_str or None,
                new_value=new_str or None,
                source=source,
            ))
        if entries:
            ClientProfileHistory.objects.bulk_create(entries)


class ClientProfile(_AuditedModel):

    PROVINCE = [('AROB','AROB'),('CENTRAL','CENTRAL'),('ENGA','ENGA'),('EAST SEPIK','EAST SEPIK'),('EHP','EHP'),('ENB','ENBP'),
    ('HELA','HELA'), ('JIWAKA','JIWAKA'),('MADANG','MADANG'),('MANUS','MANUS'),('MOROBE', 'MOROBE'),('NCD','NCD'),('NEW IRELAND','NEW IRELAND'),('ORO','ORO'),
    ('SHP','SHP'),('SIMBU','SIMBU'), ('WESTERN','WESTERN'), ('WEST SEPIK','WEST SEPIK'), ('WHP','WHP'), ('WNB','WNBP'),
    ]

    DCC_STATUS_CHOICES = [
        ('DEFAULT','DEFAULT'),
        ('RECOVERY','RECOVERY'),
        ('BAD','BAD'),
        ('BACKLIST','BLACKLIST')
    ]

    # A client keeps exactly one profile per tenant (LUID) — re-registering or
    # re-syncing must update that same row, never create a duplicate.
    class Meta:
        unique_together = [('LUID', 'CUID')]

    _history_excluded_fields = ('id', 'created_at', 'updated_at', 'user_profile')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #unique identifiers
    initial_dcc = models.CharField(max_length=100,null=True, blank=True)
    CUID = models.CharField(max_length=100,null=True, blank=True)
    LUID = models.CharField(max_length=100,null=True, blank=True)
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='client_owner', null=True, blank=True)

    credit_rating = models.DecimalField(max_digits=5, decimal_places=2, null=True, default=100.00)
    number_of_loans = models.IntegerField(null=True, blank = True, default=0)
    number_of_flagged_loans = models.IntegerField(null=True, blank = True, default=0)
    repayment_limit = models.DecimalField(verbose_name="Borrower's Limit:", max_digits=8, decimal_places=2, null=True, blank=True, default=0)

    client_type = models.CharField(max_length=20, choices=[('INDIVIDUAL','INDIVIDUAL'),('BUSINESS','BUSINESS')], default='NOT SPECIFIED', null=True, blank=True)
    #basic
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50)
    nick_name = models.CharField(max_length=50,null=True, blank=True)
    other_names = models.CharField(max_length=255,null=True, blank=True)
    gender = models.CharField(max_length=6, choices=[('MALE','MALE'),('FEMALE','FEMALE')], default='', null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(max_length=10, choices=[('SINGLE','SINGLE'),('MARRIED','MARRIED'),('DE-FACTO','DE-FACTO'),('DIVORCED','DIVORCED'),('WIDOWED','WIDOWED')], default='', null=True, blank=True)
    
    #contact
    email = models.EmailField(null=True, blank=True)
    mobile1 = models.IntegerField(null=True, blank = True)
    
    #personal_ID
    nid_number = models.CharField(max_length=20, null=True, blank=True)
    passport_number = models.CharField(max_length=20, null=True, blank=True)
    drivers_license_number = models.CharField(max_length=20, null=True, blank=True)
    super_member_code = models.CharField(max_length=20, null=True, blank=True)

    #personal_info
    place_of_origin = models.TextField(max_length=255, null=True, blank=True)
    province_of_origin = models.CharField('Province of Origin', max_length=20, choices=PROVINCE, null=True, blank=True, default="Not Specified")
    permanent_address = models.TextField(max_length=255, null=True, blank=True)
    
    #checks
    has_loan = models.BooleanField(default=False)
    dcc_flagged = models.BooleanField(default=False)
    dcc_status = models.CharField('DCC Status', max_length=20, choices=DCC_STATUS_CHOICES, null=True, blank=True, default="CLEAR")
    
    #has_arrears = models.BooleanField(default=False)
    public_listing = models.BooleanField(default=False)
    public_search = models.BooleanField(default=False)
    
    
    #comments
    dcc_comment = models.CharField(max_length=255,null=True, blank = True, default='')
    cdb_comment = models.CharField(max_length=255,null=True, blank = True, default='')
    notes = models.TextField(max_length=255, null=True, blank=True)

    vetted = models.BooleanField(default=False)
    vetting_status = models.CharField(max_length=20, choices=[('REVIEW','REVIEW'),('HOLD','HOLD'),('QUESTION','QUESTION')], default='REVIEW', null=True, blank=True)
    
    public_category = models.CharField(max_length=20, choices=[('GOOD CUSTOMER','GOOD CUSTOMER'),('IN DEFAULT','IN DEFAULT'),('IN RECOVERY','IN RECOVERY'),('HAS A BAD LOAN','HAS A BAD LOAN'),('BLACKLISTED','BLACKLISTED')], default='GOOD CUSTOMER', null=True, blank=True)
    
    
    def __str__(self):
        return f'{self.first_name} {self.last_name}'


def matched_profiles(seed):
    """Resolve a seed set of ClientProfile rows to the ONE person they belong
    to: every profile in the DCC database for that person, across all tenants.

    A person borrows from several lenders, so DCC holds one ClientProfile per
    (tenant LUID, client CUID) pair — but there is only one real Peter John,
    and he must have exactly one credit rating. Profiles are merged when they
    share a hard identifier (NID / passport / driver's licence number) or the
    same first+last name AND date of birth (business rule: two different
    people with the same full name are never born on the same day).

    The expansion is transitive: if profile A shares an NID with B, and B
    shares name+DOB with C, all three are the same person. Name-only matches
    (no DOB and no shared ID) are deliberately NOT merged — five Peter Johns
    with different birthdays stay five different people.

    Pairs an admin has resolved as "different people" (IdentityExclusion,
    from the SaaS Admin Identity Resolution queue) are never re-merged."""
    profiles = {p.pk: p for p in seed}
    if not profiles:
        return []

    for _ in range(5):  # transitive closure, capped to keep pathological data safe
        query = models.Q(pk=None)
        for p in profiles.values():
            if p.nid_number and p.nid_number.strip():
                query |= models.Q(nid_number__iexact=p.nid_number.strip())
            if p.passport_number and p.passport_number.strip():
                query |= models.Q(passport_number__iexact=p.passport_number.strip())
            if p.drivers_license_number and p.drivers_license_number.strip():
                query |= models.Q(drivers_license_number__iexact=p.drivers_license_number.strip())
            if p.first_name and p.last_name and p.date_of_birth:
                query |= models.Q(
                    first_name__iexact=p.first_name.strip(),
                    last_name__iexact=p.last_name.strip(),
                    date_of_birth=p.date_of_birth,
                )
        excluded = IdentityExclusion.partners_of(profiles.keys())
        found = (ClientProfile.objects.filter(query)
                 .exclude(pk__in=profiles.keys())
                 .exclude(pk__in=excluded))
        new = {p.pk: p for p in found}
        if not new:
            break
        profiles.update(new)

    return list(profiles.values())


class ClientProfileHistory(models.Model):
    """Full audit trail for one tenant's copy of a client. Every fact DCC has
    ever held about this ClientProfile (or its ClientEmployer / ClientBankAccount
    rows) gets one entry per change — the very first value included, not just
    edits — so nothing is ever only overwritten in place. See _AuditedModel."""
    SOURCE_CHOICES = [
        ('SYNC', 'Tenant Sync'),
        ('MANUAL', 'DCC Staff'),
        ('SYSTEM', 'System'),
    ]

    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='history')
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='SYNC')

    class Meta:
        ordering = ['-changed_at']
        indexes = [models.Index(fields=['client', '-changed_at'])]
        verbose_name_plural = 'Client profile history'

    def __str__(self):
        return f'{self.client} · {self.field_name}: {self.old_value!r} → {self.new_value!r}'


class IdentityExclusion(models.Model):
    """A human decision that two profiles are NOT the same person. The
    matcher respects these permanently, so two real Peter Johns an admin has
    separated are never re-merged. Pairs are stored normalised (low id
    first)."""
    profile_a = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='exclusions_a')
    profile_b = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='exclusions_b')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        unique_together = [('profile_a', 'profile_b')]

    def __str__(self):
        return f'NOT same person: {self.profile_a_id} <-> {self.profile_b_id}'

    @classmethod
    def separate(cls, profiles, by=''):
        """Record that every pair among ``profiles`` is a different person."""
        ids = sorted({p.pk for p in profiles})
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                cls.objects.get_or_create(profile_a_id=a, profile_b_id=b,
                                          defaults={'created_by': by})

    @classmethod
    def partners_of(cls, profile_ids):
        """IDs excluded against ANY of the given profile ids."""
        ids = list(profile_ids)
        out = set()
        for a, b in cls.objects.filter(
                models.Q(profile_a_id__in=ids) | models.Q(profile_b_id__in=ids)
        ).values_list('profile_a_id', 'profile_b_id'):
            out.add(a)
            out.add(b)
        return out - set(ids)


class IdentityCase(models.Model):
    """One cluster of profiles that may belong to the same person, queued for
    a human decision in SaaS Admin -> Identity Resolution.

    AUTO cases are clusters the matcher already links (shared ID or name+DOB)
    awaiting confirmation; REVIEW cases are ambiguous look-alikes (same name,
    missing or conflicting DOB) that only a human may merge."""
    KIND_CHOICES = [('AUTO', 'Auto-linked — confirm'), ('REVIEW', 'Ambiguous — needs review')]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('LINKED', 'Confirmed same person'),
        ('MERGED', 'Merged into one profile'),
        ('DISMISSED', 'Different people'),
    ]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='REVIEW')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    signature = models.CharField(max_length=64, unique=True, help_text='Stable hash of the sorted member ids (dedupes rescans).')
    member_ids = models.JSONField(default=list)
    display_name = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.CharField(max_length=100, blank=True, default='')
    primary = models.ForeignKey(ClientProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='identity_primary_cases')
    note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['status', '-created_at']

    def __str__(self):
        return f'{self.display_name or "Identity case"} [{self.kind}/{self.status}] x{len(self.member_ids)}'

    def members(self):
        profiles = ClientProfile.objects.filter(pk__in=self.member_ids).select_related('user_profile')
        return sorted(profiles, key=lambda p: self.member_ids.index(p.pk) if p.pk in self.member_ids else 0)


def _case_signature(ids):
    import hashlib
    return hashlib.sha256(','.join(str(i) for i in sorted(ids)).encode()).hexdigest()


def scan_identity_cases():
    """Scan the whole database for clusters needing a human decision and
    (re)queue them as PENDING IdentityCases. Returns counts.

    - AUTO: matcher-linked clusters (>1 profile) with no case yet.
    - REVIEW: same normalised first+last name spread across profiles the
      matcher does NOT link (missing/conflicting DOB, no shared ID) and not
      already ruled different people."""
    from collections import defaultdict

    created_auto = created_review = 0
    seen = set()

    # AUTO clusters
    for profile in ClientProfile.objects.all().only('id'):
        if profile.id in seen:
            continue
        cluster = matched_profiles(ClientProfile.objects.filter(pk=profile.id))
        ids = sorted(p.pk for p in cluster)
        seen.update(ids)
        if len(ids) < 2:
            continue
        sig = _case_signature(ids)
        first = cluster[0]
        _, was_created = IdentityCase.objects.get_or_create(
            signature=sig,
            defaults={
                'kind': 'AUTO',
                'member_ids': ids,
                'display_name': f'{first.first_name} {first.last_name}'.strip()[:120],
            },
        )
        created_auto += 1 if was_created else 0

    # REVIEW groups: same name, not auto-linked
    groups = defaultdict(list)
    for p in ClientProfile.objects.exclude(first_name='').exclude(last_name=''):
        key = (p.first_name.strip().lower(), p.last_name.strip().lower())
        groups[key].append(p)

    for (_fn, _ln), members in groups.items():
        if len(members) < 2:
            continue
        # split the name-group into its auto-clusters; if more than one
        # cluster remains, a human should look at it
        remaining = {p.pk: p for p in members}
        clusters = []
        while remaining:
            any_id = next(iter(remaining))
            cluster = matched_profiles(ClientProfile.objects.filter(pk=any_id))
            cluster_ids = {p.pk for p in cluster} & set(remaining)
            clusters.append(sorted(cluster_ids))
            for cid in cluster_ids:
                remaining.pop(cid, None)
        if len(clusters) < 2:
            continue
        ids = sorted(p.pk for p in members)
        excluded = IdentityExclusion.partners_of(ids)
        # if every cross-cluster pair is already excluded, admins have ruled
        if all(set(c) <= excluded | set(clusters[0]) for c in clusters[1:]) and excluded:
            continue
        sig = _case_signature(ids)
        if IdentityCase.objects.filter(signature=sig).exists():
            continue
        IdentityCase.objects.create(
            kind='REVIEW',
            signature=sig,
            member_ids=ids,
            display_name=f'{members[0].first_name} {members[0].last_name}'.strip()[:120],
        )
        created_review += 1

    return {'auto': created_auto, 'review': created_review}


def merge_profiles(primary, duplicates, by=''):
    """Fold duplicate profiles into ``primary``: every related record (loans,
    transactions, history, employers, bank accounts, uploads, addresses,
    contacts, payslips, business links) is re-pointed, blank fields on the
    primary are filled from the duplicates, and the duplicates are deleted.

    Intended for true duplicates. Merging profiles from DIFFERENT tenants
    removes that tenant's (LUID, CUID) row, which the next feed sync will
    recreate — use a LINK resolution for cross-tenant profiles instead."""
    from loan.models import Loan
    from transaction.models import Transaction

    fill_fields = [
        'middle_name', 'nick_name', 'other_names', 'gender', 'date_of_birth',
        'marital_status', 'email', 'mobile1', 'nid_number', 'passport_number',
        'drivers_license_number', 'super_member_code', 'place_of_origin',
        'province_of_origin', 'permanent_address',
    ]

    for dupe in duplicates:
        if dupe.pk == primary.pk:
            continue
        Loan.objects.filter(owner=dupe).update(owner=primary)
        Transaction.objects.filter(owner=dupe).update(owner=primary)
        ClientProfileHistory.objects.filter(client=dupe).update(client=primary)
        ClientEmployer.objects.filter(client=dupe).update(client=primary)
        ClientBankAccount.objects.filter(client=dupe).update(client=primary)
        ClientUpload.objects.filter(client=dupe).update(client=primary)
        ClientAddress.objects.filter(client=dupe).update(client=primary)
        ClientContact.objects.filter(client=dupe).update(client=primary)
        Payslip.objects.filter(client=dupe).update(client=primary)
        BusinessProfile.objects.filter(business_owner=dupe).update(business_owner=primary)
        ClientCreditScore.objects.filter(client=dupe).delete()

        for field in fill_fields:
            if not getattr(primary, field) and getattr(dupe, field):
                setattr(primary, field, getattr(dupe, field))
        primary.dcc_flagged = primary.dcc_flagged or dupe.dcc_flagged
        primary.has_loan = primary.has_loan or dupe.has_loan

        ClientProfileHistory.objects.create(
            client=primary, field_name='merged_from',
            old_value=f'{dupe.LUID}/{dupe.CUID}',
            new_value=f'merged by {by or "admin"}', source='SYSTEM',
        )
        dupe.delete()

    primary.save(_history_source='SYSTEM')
    ClientCreditScore.ensure(primary, profiles=matched_profiles(
        ClientProfile.objects.filter(pk=primary.pk)))
    return primary


class BusinessProfile(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    buid = models.CharField(max_length=20,null=True, blank=True)
    ref = models.CharField(max_length=20, null=True, blank=True, default='')
    public_listing = models.BooleanField(default=False)
    public_search = models.BooleanField(default=False)
    credit_rating = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=100)
    
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='record_owner', null=True, blank=True)

    business_owner = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='business_owner', null=True, blank=True)
    category = models.CharField(max_length=20, choices=[('SOLE TRADER','SOLE TRADER'),('SME','SME'),('MSME','MSME'),('COMPANY','COMPANY')], default='SME', null=True, blank=True)
    trading_name =  models.CharField(max_length=255, null=True, blank=True, default='')
    registered_name = models.CharField(max_length=255, null=True, blank=True, default='') 
    business_address = models.CharField(max_length=255, null=True, blank=True, default='')
    email = models.EmailField(null=True, blank = True)
    phone = models.CharField(max_length=10, null=True, blank=True, default='')
    website = models.CharField(max_length=100, null=True, blank=True, default='')
    ipa_registration_number = models.CharField(max_length=20, null=True, blank=True)
    tin_number = models.CharField(max_length=20, null=True, blank=True)
    #default data
    amount = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)
    date_of_committment = models.DateField(null=True, blank=True)

    vetted = models.BooleanField(default=False)
    vetting_status = models.CharField(max_length=20, choices=[('REVIEW','REVIEW'),('HOLD','HOLD'),('QUESTION','QUESTION'),('VETTED','VETTED')], default='REVIEW', null=True, blank=True)

    public_category = models.CharField(max_length=20, choices=[('GOOD CUSTOMER','GOOD CUSTOMER'),('IN DEFAULT','IN DEFAULT'),('IN RECOVERY','IN RECOVERY'),('HAS A BAD LOAN','HAS A BAD LOAN'),('BLACKLISTED','BLACKLISTED')], default='GOOD CUSTOMER', null=True, blank=True)
    
class RatingRule(models.Model):
    """One configurable factor of the benchmark credit score.

    Every action DCC studies about a client (completed loans, defaults,
    identity changes, past recovery episodes, ...) has one rule row: how many
    points it is worth, whether it increases or reduces the rating, and an
    optional cap on the total points that factor can contribute. Editable in
    SaaS Admin -> Rating Calculation; missing rows are auto-seeded with the
    defaults below."""

    INCREASE = 'INCREASE'
    REDUCE = 'REDUCE'

    # action key -> (label, direction, points per occurrence, cap or None, help)
    DEFAULTS = {
        'BASE_SCORE': ('Starting score for every client', INCREASE, 500, None,
                       'Every client starts at this score before any factor is applied.'),
        'COMPLETED_LOAN': ('Completed loan', INCREASE, 30, 150,
                           'Per loan fully repaid, any lender.'),
        'TENURE_YEAR': ('Year of borrowing history', INCREASE, 10, 50,
                        'Per year between the first and last funded loan.'),
        'ACTIVE_MONTH': ('Month with repayment activity', INCREASE, 5, 60,
                         'Per distinct month with a repayment transaction on record.'),
        'MULTI_LENDER_CLEAN': ('Clean record across 2+ lenders', INCREASE, 20, None,
                               'One-off bonus when 2+ tenants report the client and there are no defaults or past bad episodes.'),
        'DEFAULTED_LOAN': ('Defaulted loan', REDUCE, 150, None,
                           'Per loan currently in DEFAULTED status.'),
        'ARREARS_LOAN': ('Active loan in arrears', REDUCE, 50, None,
                         'Per active loan carrying arrears.'),
        'RECOVERY_LOAN': ('Loan in recovery', REDUCE, 100, None,
                          'Per loan in RECOVERY.'),
        'PAST_STATUS_EVENT': ('Past default/recovery/bad episode', REDUCE, 30, 150,
                              'Per historical DEFAULT/RECOVERY/BAD/BLACKLIST episode found in the audit trail, even if since cleared.'),
        'IDENTITY_CHANGE': ('Identity detail changed', REDUCE, 15, 90,
                            'Per change to name/DOB/ID numbers beyond the first two (two corrections are free).'),
        'DCC_FLAGGED': ('Currently flagged by the bureau', REDUCE, 100, None,
                        'One-off when any profile of the client is DCC-flagged.'),
        'STATUS_DEFAULT_BAD': ('Current status DEFAULT or BAD', REDUCE, 80, None,
                               'One-off when any profile has status DEFAULT or BAD.'),
        'STATUS_RECOVERY': ('Current status RECOVERY', REDUCE, 60, None,
                            'One-off when any profile has status RECOVERY.'),
        'BLACKLIST_CAP': ('Blacklisted score ceiling', REDUCE, 49, None,
                          'A blacklisted client\'s score can never exceed this number of points.'),
    }

    action = models.CharField(max_length=30, unique=True)
    label = models.CharField(max_length=120)
    direction = models.CharField(max_length=10, choices=[(INCREASE, 'Increase rating'), (REDUCE, 'Reduce rating')], default=REDUCE)
    points = models.PositiveIntegerField(default=0, help_text='Points per occurrence of this action.')
    cap = models.PositiveIntegerField(null=True, blank=True, help_text='Optional maximum total points this factor can contribute.')
    enabled = models.BooleanField(default=True)
    help_text = models.CharField(max_length=255, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['action']

    def __str__(self):
        sign = '+' if self.direction == self.INCREASE else '-'
        return f'{self.label}: {sign}{self.points}'

    def contribution(self, count=1):
        """Signed score contribution for ``count`` occurrences of this action."""
        if not self.enabled or count <= 0:
            return 0
        total = self.points * count
        if self.cap is not None and self.cap > 0:
            total = min(total, self.cap)
        return total if self.direction == self.INCREASE else -total

    @classmethod
    def as_map(cls):
        """All rules keyed by action, seeding any missing rows with defaults."""
        rules = {r.action: r for r in cls.objects.all()}
        for action, (label, direction, points, cap, help_text) in cls.DEFAULTS.items():
            if action not in rules:
                rules[action] = cls.objects.create(
                    action=action, label=label, direction=direction,
                    points=points, cap=cap, help_text=help_text,
                )
        return rules


class ClientCreditScore(models.Model):
    """DCC's benchmark credit score for a client: a single 0-1000 number (plus
    letter grade) computed from everything the bureau knows about the person
    across every tenant — loans, repayment transactions, and the full
    ClientProfileHistory audit trail (identity churn, past default/recovery
    episodes). Recomputed on every paid credit-check view and nightly for the
    whole database. This is the single source of truth lenders can use for
    auto credit decisions."""
    GRADE_CHOICES = [
        ('AAA', 'AAA – Exceptional'),
        ('AA',  'AA – Excellent'),
        ('A',   'A – Very Good'),
        ('BBB', 'BBB – Good'),
        ('BB',  'BB – Fair'),
        ('B',   'B – Below Average'),
        ('CCC', 'CCC – Poor'),
        ('CC',  'CC – Bad'),
        ('C',   'C – Very Bad'),
    ]
    client = models.OneToOneField(ClientProfile, on_delete=models.CASCADE, related_name='credit_score')
    score = models.PositiveIntegerField(default=500, help_text='0–1000 composite credit score.')
    grade = models.CharField(max_length=5, choices=GRADE_CHOICES, default='BBB')
    computed_at = models.DateTimeField(auto_now=True)
    # factor breakdown (stored for display / audit)
    total_loans = models.IntegerField(default=0)
    completed_loans = models.IntegerField(default=0)
    active_loans = models.IntegerField(default=0)
    defaulted_loans = models.IntegerField(default=0)
    arrears_loans = models.IntegerField(default=0)
    recovery_loans = models.IntegerField(default=0)
    total_borrowed = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_outstanding = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # history/activity factors (from the ClientProfileHistory audit trail)
    tenants_reporting = models.IntegerField(default=0, help_text='Distinct tenants holding a profile for this person.')
    identity_changes = models.IntegerField(default=0, help_text='Times identity fields (name/DOB/IDs) were changed after first capture.')
    status_events = models.IntegerField(default=0, help_text='Historical DEFAULT/RECOVERY/BAD/BLACKLIST episodes, even if since cleared.')
    months_active = models.IntegerField(default=0, help_text='Distinct months with repayment activity on record.')

    def __str__(self):
        return f'{self.client} – {self.grade} ({self.score}/1000)'

    @staticmethod
    def _score_to_grade(score):
        if score >= 850: return 'AAA'
        if score >= 750: return 'AA'
        if score >= 650: return 'A'
        if score >= 550: return 'BBB'
        if score >= 450: return 'BB'
        if score >= 350: return 'B'
        if score >= 250: return 'CCC'
        if score >= 150: return 'CC'
        return 'C'

    @classmethod
    def ensure(cls, primary, profiles=None):
        """Get-or-create the score row for the person's primary profile and
        recompute it from the matched profile set. Returns the score."""
        obj, _ = cls.objects.get_or_create(client=primary)
        obj.recompute(profiles=profiles)
        return obj

    def recompute(self, profiles=None):
        """Recalculate the benchmark score from every fact DCC holds about the
        person and save. ``profiles`` is the matched cross-tenant profile set
        (see matched_profiles); defaults to just this profile.

        The resulting 0-100 rating (score / 10) is also written back onto every
        matched ClientProfile.credit_rating so tenant screens and API feeds all
        quote the same number."""
        from decimal import Decimal as _D

        from django.db.models import Q as _Q, Sum as _Sum

        from loan.models import Loan
        from transaction.models import Transaction

        profiles = profiles or [self.client]
        profile_ids = [p.pk for p in profiles]

        # All loan records for the person, across every lender tenant. Loans
        # are linked either by FK owner or by the raw (LUID, UID) pair synced
        # from the tenant feed before the owner FK was resolved.
        loan_q = _Q(owner_id__in=profile_ids)
        txn_q = _Q(owner_id__in=profile_ids)
        for p in profiles:
            if p.CUID:
                loan_q |= _Q(LUID=p.LUID, UID=p.CUID)
                txn_q |= _Q(luid=p.LUID, uid=p.CUID)
        loans = Loan.objects.filter(loan_q).distinct()

        total = loans.count()
        completed = loans.filter(status='COMPLETED').count()
        active = loans.filter(funded_category='ACTIVE').count()
        defaulted = loans.filter(status='DEFAULTED').count()
        arrears = loans.filter(funded_category='ACTIVE', total_arrears__gt=0).count()
        recovery = loans.filter(funded_category='RECOVERY').count()
        total_borrowed = loans.aggregate(s=_Sum('amount'))['s'] or 0
        total_outstanding = loans.aggregate(s=_Sum('total_outstanding'))['s'] or 0

        # Repayment activity: distinct months with money coming in.
        months_active = (Transaction.objects.filter(txn_q, credit__gt=0)
                         .dates('date', 'month').count())

        # Study the audit trail — every version of the client ever recorded.
        history = ClientProfileHistory.objects.filter(client_id__in=profile_ids)
        identity_fields = ('first_name', 'last_name', 'date_of_birth',
                           'nid_number', 'passport_number', 'drivers_license_number')
        identity_changes = history.filter(
            field_name__in=identity_fields, old_value__isnull=False).count()
        status_events = history.filter(
            field_name='dcc_status',
            new_value__in=['DEFAULT', 'RECOVERY', 'BAD', 'BACKLIST', 'BLACKLIST'],
        ).count()
        tenants_reporting = len({p.LUID for p in profiles if p.LUID})

        # Score every action using the configurable rules
        # (SaaS Admin -> Rating Calculation).
        rules = RatingRule.as_map()
        score = rules['BASE_SCORE'].points if rules['BASE_SCORE'].enabled else 500

        # Positive: completed loans, tenure, repayment activity, breadth
        score += rules['COMPLETED_LOAN'].contribution(completed)
        tenure_years = 0
        if loans.filter(funding_date__isnull=False).count() >= 2:
            dated = loans.filter(funding_date__isnull=False).order_by('funding_date')
            tenure_years = (dated.last().funding_date - dated.first().funding_date).days // 365
        score += rules['TENURE_YEAR'].contribution(tenure_years)
        score += rules['ACTIVE_MONTH'].contribution(months_active)
        if tenants_reporting > 1 and defaulted == 0 and status_events == 0:
            score += rules['MULTI_LENDER_CLEAN'].contribution(1)
        # Negative: current bad loan behaviour
        score += rules['DEFAULTED_LOAN'].contribution(defaulted)
        score += rules['ARREARS_LOAN'].contribution(arrears)
        score += rules['RECOVERY_LOAN'].contribution(recovery)
        # Negative: past episodes from the audit trail (even if since cleared)
        score += rules['PAST_STATUS_EVENT'].contribution(status_events)
        score += rules['IDENTITY_CHANGE'].contribution(max(identity_changes - 2, 0))
        # Bureau flags on the current profile(s)
        if any(p.dcc_flagged for p in profiles):
            score += rules['DCC_FLAGGED'].contribution(1)
        statuses = {p.dcc_status for p in profiles}
        if statuses & {'DEFAULT', 'BAD'}:
            score += rules['STATUS_DEFAULT_BAD'].contribution(1)
        if 'RECOVERY' in statuses:
            score += rules['STATUS_RECOVERY'].contribution(1)
        if any(p.public_category == 'BLACKLISTED' for p in profiles) and rules['BLACKLIST_CAP'].enabled:
            score = min(score, rules['BLACKLIST_CAP'].points)

        score = max(0, min(1000, score))

        self.score = score
        self.grade = self._score_to_grade(score)
        self.total_loans = total
        self.completed_loans = completed
        self.active_loans = active
        self.defaulted_loans = defaulted
        self.arrears_loans = arrears
        self.recovery_loans = recovery
        self.total_borrowed = total_borrowed
        self.total_outstanding = total_outstanding
        self.tenants_reporting = tenants_reporting
        self.identity_changes = identity_changes
        self.status_events = status_events
        self.months_active = months_active
        self.save()

        # One consistent 0-100 rating everywhere (queryset update: no history noise)
        ClientProfile.objects.filter(pk__in=profile_ids).update(
            credit_rating=_D(score) / _D(10))


class UserProfileUpload(models.Model):
    UPLOAD_TYPE_CHOICES = [('RECORD','RECORD')]
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='userprofile_uploads')
    upload_type = models.CharField(max_length=20, choices=UPLOAD_TYPE_CHOICES, default='', null=True, blank=True)
    upload_file = models.FileField(upload_to='uploads/', null=True, blank=True)
    upload_file_url = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    processed = models.BooleanField(default=False)

class ClientUpload(models.Model):
    UPLOAD_TYPE_CHOICES = [('PROFILE_PIC','PROFILE_PIC'),('NID','NID'),('PASSPORT','PASSPORT'),
    ('DRIVERS_LICENSE','DRIVERS_LICENSE'),('SUPER_ID','SUPER_ID'),
    ('WORK_ID','WORK_ID'),('PAYSLIP','PAYSLIP'),
    ('BANK_STATEMENT','BANK_STATEMENT'),('LOAN_STATEMENT','LOAN_STATEMENT'),
    ('BANK_STANDING_ORDER','BANK_STANDING_ORDER'),
    ('TIN_CERTIFICATE','TIN_CERTIFICATE'),('LOGO','LOGO'),('IPA_CERTIFICATE','IPA_CERTIFICATE'),
    ('CASH_FLOW','CASH_FLOW'),
    ('OTHERS','OTHERS')
    ]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_uploads')
    upload_type = models.CharField(max_length=20, choices=UPLOAD_TYPE_CHOICES, default='', null=True, blank=True)
    upload_file = models.FileField(upload_to='uploads/', null=True, blank=True)
    upload_file_url = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)

class ClientAddress(models.Model):
    PROVINCE_CHOICES = [('AROB','AROB'),('CENTRAL','CENTRAL'),('ENGA','ENGA'),('EAST SEPIK','EAST SEPIK'),('EHP','EHP'),('ENB','ENBP'),
    ('HELA','HELA'), ('JIWAKA','JIWAKA'),('MADANG','MADANG'),('MANUS','MANUS'),('MOROBE', 'MOROBE'),('NCD','NCD'),('NEW IRELAND','NEW IRELAND'),('ORO','ORO'),
    ('SHP','SHP'),('SIMBU','SIMBU'), ('WESTERN','WESTERN'), ('WEST SEPIK','WEST SEPIK'), ('WHP','WHP'), ('WNB','WNBP'),
    ]

    ADDRESS_TYPE_CHOICES = [('RESIDENTIAL','RESIDENTIAL'),('POSTAL','POSTAL'),('BUSINESS','BUSINESS'),('OTHERS','OTHERS')]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_address')
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default='', null=True, blank=True)
    address = models.TextField(max_length=255, null=True, blank=True)
    residential_province = models.CharField(max_length=20, choices=PROVINCE_CHOICES, null=True, blank=True, default="Not Specified")
    resident_owner = models.CharField(max_length=10, choices=[('SELF','SELF'),('RELATIVES','RELATIVES'),('RENTAL','RENTAL'),('WORK-HOUSE','WORK_HOUSE'),('OTHERS','OTHERS')], default='',null=True, blank=True)

class ClientContact(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_contact')

    email1 = models.EmailField(null=True, blank=True)
    email2 = models.EmailField(null=True, blank=True)
    mobile1 = models.IntegerField(null=True, blank=True)
    mobile2 = models.IntegerField(null=True, blank=True)
    
class ClientEmployer(_AuditedModel):
    _history_prefix = 'employer.'
    _history_excluded_fields = ('id', 'created_at', 'updated_at', 'client')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #employer information
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_employer', null=True, blank=True,)
    sector  = models.CharField(max_length=10, choices=[('PUBLIC','PUBLIC'),('PRIVATE','PRIVATE'),('SOE','SOE'),('SME','SME'),('NGO','NGO'),('OTHERS','OTHERS')], default='NA', null=True, blank=True)
    employer = models.CharField(max_length=50,null=True, blank=True, default='')
    job_title = models.CharField(max_length=255,null=True, blank=True, default='')
    work_id_number = models.CharField(max_length=20, null=True, blank=True)
    office_address = models.TextField(max_length=255, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    pay_frequency = models.CharField(max_length=100, choices=[('FN','FORTNIGHTLY'),('MN','MONTHLY')], default='FN', null=True, blank=True)
    last_paydate = models.DateField(null=True, blank=True)
    gross_pay = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)

    work_phone = models.CharField(max_length=20, blank = True, null=True)
    work_email = models.EmailField(verbose_name='Work Email Address', max_length=50, blank = True, null=True)

class ClientBankAccount(_AuditedModel):
    _history_prefix = 'bank.'
    _history_excluded_fields = ('id', 'created_at', 'updated_at', 'client')

    BANK_CHOICES = [('BSP', 'BSP'),('KINA','KINA'),
    ('WESTPAC','WESTPAC'),('CREDIT BANK','CREDIT BANK'),('TISA BANK','TISA BANK')
    ]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #bankaccount info
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_bankaccount', null=True, blank=True,)
    bank = models.CharField(max_length=30, choices=BANK_CHOICES, default='', null=True, blank=True)
    account_name =  models.CharField(max_length=100, null=True, blank=True, default='')
    account_number = models.CharField(max_length=30,null=True, blank = True)
    branch_bsb = models.CharField(max_length=30,null=True, blank = True, default='')
    branch_name = models.CharField(max_length=100, null=True, blank=True, default='')

class Payslip(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #payslip info
    
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_payslip', null=True, blank=True,)
    employer = models.ForeignKey(ClientEmployer, on_delete=models.CASCADE, related_name='employer_payslip', null=True, blank=True,)
    pay_frequency = models.CharField(max_length=2, choices=[('FN','FORTNIGHTLY'),('MN','MONTHLY')], default='FN', null=True, blank=True)
    last_paydate = models.DateField(null=True, blank=True)

    gross_pay = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)
    total_deductions = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)
    net_pay = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)

    pay_slip = models.FileField(upload_to='uploads/', null=True, blank=True)
    pay_slip_url = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)