from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('email',)

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email',)
        
        from django import forms

from django import forms

class PaymentForm(forms.Form):
    PAYMENT_CHOICES = [
        ('paypay', 'PayPay'),
        ('convenience_store', 'コンビニ払い'),
        ('credit_card', 'クレジットカード'),
        ('merupay', 'MeruPay'),
        ('other', 'その他'),
    ]
    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect,
        label='お支払い方法'
    )


