from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from .models import User


class StyledAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Login yoki parol noto‘g‘ri, yoki hisob o‘chirilgan.",
        "inactive": "Hisob faol emas.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"placeholder": "Login", "autocomplete": "username", "autocapitalize": "none", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update({"placeholder": "Parol", "autocomplete": "current-password"})
        self.fields["username"].label = "Login"
        self.fields["password"].label = "Parol"


class UserCreateForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "role")


class UserEditForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"
