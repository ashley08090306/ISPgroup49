from django.shortcuts import render, redirect
from django.contrib.auth import login
from .models import User, ShippingAddress

def home(request):
    return render(request, 'home.html')

def register(request):
    if request.method == 'POST':
        # 1. 获取基础信息
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role') # 获取用户选的角色 ('customer' 或 'vendor')

        # 2. 获取地址信息
        country = request.POST.get('country')
        city = request.POST.get('city')
        district = request.POST.get('district')
        street = request.POST.get('street')
        detail = request.POST.get('detail_address')

        # 3. 核心逻辑判断
        # 如果是顾客，必须填地址 (Requirement A1)
        if role == 'customer':
            if not (country and city and street and detail):
                return render(request, 'register.html', {'error': 'Customers should provide a complete address during registration!'})

        # 4. 开始创建用户
        if username and password:
            try:
                # 4.1 创建 User 表记录
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role=role
                )

                # 4.2 只有当角色是 'customer' 时，才创建 ShippingAddress 表记录
                # 商家不需要地址，所以这里跳过
                if role == 'customer':
                    ShippingAddress.objects.create(
                        user=user,
                        country=country,
                        city=city,
                        district=district,
                        street=street,
                        detail_address=detail
                    )

                # 5. 注册成功，直接登录
                login(request, user)

                # 6. 登录后去哪里？(根据角色跳转)
                # 如果是商家，去后台；如果是顾客，去首页
                # 目前你们还没做后台页面，暂时都先去 home
                return redirect('home')

            except Exception as e:
                # 如果用户名已存在等错误，显示出来
                return render(request, 'register.html', {'error': str(e)})

    return render(request, 'register.html')