from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from .models import User, ShippingAddress

# 1. 首页视图：增加逻辑，如果是商家，强制跳转到 Dashboard
def home(request):
    if request.user.is_authenticated and getattr(request.user, 'role', '') == 'vendor':
        return redirect('vendor_dashboard')
    return render(request, 'home.html')

# 2. 商家仪表盘视图
@login_required
def vendor_dashboard(request):
    # 安全检查：如果不是 vendor，踢回首页
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    # 这里以后可以从数据库获取真实数据
    context = {
        'vendor_name': request.user.username,
        # 'total_sales': 0,
        # 'order_count': 0
    }
    return render(request, 'vendor_dashboard.html', context)

# 3. 商家店铺信息/Profile (新增)
@login_required
def vendor_myshop(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    user = request.user
    # 获取商家的地址信息（假设复用 ShippingAddress 模型作为商家地址）
    address = ShippingAddress.objects.filter(user=user).first()

    if request.method == 'POST':
        # 更新基本信息
        user.username = request.POST.get('shop_name')
        user.email = request.POST.get('email')
        user.save()

        # 更新或创建地址信息
        if not address:
            address = ShippingAddress(user=user)

        address.country = request.POST.get('country')
        address.city = request.POST.get('city')
        address.district = request.POST.get('district')
        address.street = request.POST.get('street')
        address.detail_address = request.POST.get('detail_address')
        address.save()

        return redirect('vendor_myshop')

    context = {
        'user': user,
        'address': address
    }
    return render(request, 'vendor_myshop.html', context)

# 4. 商家商品管理视图
@login_required
def vendor_products(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')
    return render(request, 'vendor_products.html')

@login_required
def vendor_add_product(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')
    # 这里处理 POST 请求添加商品
    return render(request, 'vendor_add_product.html')

# 5. 商家订单管理视图
@login_required
def vendor_orders(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')
    return render(request, 'vendor_orders.html')

# 注册视图
def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')

        country = request.POST.get('country')
        city = request.POST.get('city')
        district = request.POST.get('district')
        street = request.POST.get('street')
        detail = request.POST.get('detail_address')

        if role == 'customer':
            if not (country and city and street and detail):
                return render(request, 'register.html', {'error': 'Customers should provide a complete address during registration!'})

        if username and password:
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    role=role
                )

                # 无论是 Customer 还是 Vendor，如果有地址信息都保存
                # Vendor 的地址可以作为发货地址或展示地址
                if country:
                    ShippingAddress.objects.create(
                        user=user,
                        country=country,
                        city=city,
                        district=district,
                        street=street,
                        detail_address=detail
                    )

                login(request, user)

                if role == 'vendor':
                    return redirect('vendor_dashboard')
                else:
                    return redirect('home')

            except Exception as e:
                return render(request, 'register.html', {'error': str(e)})

    return render(request, 'register.html')

# 登陆视图
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            if getattr(user, 'role', '') == 'vendor':
                return redirect('vendor_dashboard')
            else:
                return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')