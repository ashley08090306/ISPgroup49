from django.contrib.auth.backends import BaseBackend
from core.models import User

class EmailOrUsernameBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # 判断是邮箱还是用户名
        if '@' in username:
            try:
                # 如果是邮箱，查询该邮箱对应的用户
                user = User.objects.get(email=username)
                # 校验密码
                if user.check_password(password):
                    return user
            except User.DoesNotExist:
                return None  # 如果用户不存在，返回 None
        else:
            try:
                # 如果是用户名，查询该用户名对应的用户
                user = User.objects.get(username=username)
                # 校验密码
                if user.check_password(password):
                    return user
            except User.DoesNotExist:
                return None  # 如果用户不存在，返回 None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None  # 如果找不到用户，返回 None
