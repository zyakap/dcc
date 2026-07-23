from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class BorrowerAccount(models.Model):
    client    = models.OneToOneField('client.ClientProfile', on_delete=models.CASCADE, related_name='borrower_account')
    pin_hash  = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Borrower portal account'

    def __str__(self):
        return f'Borrower account for {self.client}'

    def set_pin(self, raw_pin):
        self.pin_hash = make_password(str(raw_pin))

    def check_pin(self, raw_pin):
        return check_password(str(raw_pin), self.pin_hash)
