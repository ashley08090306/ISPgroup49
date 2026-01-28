from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from core.models import User  # 确保导入的是自定义的 User 模型
from .models import ShippingAddress, Product, Category, Tag, Order, ProductImage, ShopProfile
from django.db.models import Sum, Q, F
from django.contrib.auth import authenticate
from django.utils.safestring import mark_safe
from django.urls import reverse


# ==================== 公共视图 ====================

def home(request):
    if request.user.is_authenticated and getattr(request.user, 'role', '') == 'vendor':
        return redirect('vendor_dashboard')
    return render(request, 'home.html')

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role = request.POST.get('role')

        # 地址信息
        country = request.POST.get('country')
        city = request.POST.get('city')
        district = request.POST.get('district')
        street = request.POST.get('street')
        detail = request.POST.get('detail_address')

        if password != confirm_password:
            return render(request, 'register.html', {'error': 'Passwords do not match! Please try again.'})

        if role == 'customer':
            if not (country and city and street and detail):
                return render(request, 'register.html', {'error': 'Customers should provide a complete address during registration!'})

        if username and password and email:
            try:
                # 1. 检查用户名
                if User.objects.filter(username=username).exists():
                    return render(request, 'register.html', {
                        'error': f'Username "{username}" already taken. Try adding numbers or using a different name.'
                    })

                # 2. 检查邮箱
                if User.objects.filter(email=email).exists():
                    login_url = reverse('login')
                    error_msg = mark_safe(f'Email already registered. <a href="{login_url}" class="text-dark" style="text-decoration: underline;"><strong>Log in now</strong></a>')
                    return render(request, 'register.html', {'error': error_msg})

                # 创建用户
                user = User.objects.create_user(username=username, email=email, password=password, role=role)

                if country:
                    ShippingAddress.objects.create(
                        user=user, country=country, city=city,
                        district=district, street=street, detail_address=detail
                    )

                # ✨✨✨ 【Bug 修复核心代码】 ✨✨✨
                # 必须手动指定后端，否则 login() 会因为找不到 backend 而崩溃
                user.backend = 'core.authentication.EmailOrUsernameBackend'

                login(request, user)

                if role == 'vendor':
                    return redirect('vendor_dashboard')
                else:
                    return redirect('home')

            except Exception as e:
                # 建议在开发阶段把 e 打印出来，这样看控制台就知道具体错哪了
                print(f"Registration Error: {e}")
                return render(request, 'register.html', {'error': 'Something went wrong during registration. Please try again.'})

    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        data = request.POST.copy()
        login_input = data.get('username')  # 用户填的可能是用户名，也可能是邮箱
        password_input = data.get('password')  # 用户填的密码

        user = authenticate(request, username=login_input, password=password_input)

        if user is not None:
            # 登录成功
            login(request, user)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            if getattr(user, 'role', '') == 'vendor':
                return redirect('vendor_dashboard')
            else:
                return redirect('home')
        else:
            # 登录失败
            form = AuthenticationForm(data=data)
            return render(request, 'login.html', {
                'form': form,
                'error': 'Invalid username/email or password. Please try again.'
            })

    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')


# ==================== 商家视图 (Vendor Portal) ====================


@login_required
def vendor_dashboard(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    # ✅ 新写法 (单价 * 数量)：
    total_sales_data = Order.objects.aggregate(total=Sum(F('product__price') * F('quantity')))
    total_sales = total_sales_data['total']

    # 获取所有活跃商品的数量
    active_products = Product.objects.filter(available=True).count()

    # 获取所有待处理订单的数量
    pending_orders = Order.objects.filter(status='Pending').count()

    return render(request, 'vendor_dashboard.html', {
        'total_sales': total_sales or 0,
        'active_products': active_products,
        'pending_orders': pending_orders
    })


@login_required
def vendor_myshop(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    # ✨✨✨ 核心修改：获取全局唯一的店铺配置 (ID=1) ✨✨✨
    # get_or_create 的意思是：如果有 ID=1 的记录就拿出来，没有就新建一个
    shop, created = ShopProfile.objects.get_or_create(id=1)

    if request.method == 'POST':
        # 修改公共店铺信息
        shop.shop_name = request.POST.get('shop_name')
        shop.email = request.POST.get('email')

        shop.country = request.POST.get('country')
        shop.city = request.POST.get('city')
        shop.district = request.POST.get('district')
        shop.street = request.POST.get('street')
        shop.detail_address = request.POST.get('detail_address')

        shop.save() # 保存到公共表

        return redirect('vendor_myshop')

    # 把 shop 对象传给前端，而不是传 user
    context = {
        'shop': shop
    }
    return render(request, 'vendor_myshop.html', context)

@login_required
def vendor_products(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    # 1. 获取所有商品，而不是只拿到该商家的商品
    products = Product.objects.all().order_by('-id')  # 按 ID 倒序，新加的在前面
    # 2. 获取搜索关键词 (从 URL 的 ?q=xxx 里拿)
    search_query = request.GET.get('q')

    # 3. 如果有搜索词，就进行过滤
    if search_query:
        products = products.filter(
            # Q 对象允许我们用 | (OR) 逻辑
            # A14: 搜索商品名 (icontains 忽略大小写)
            Q(product_name__icontains=search_query) |
            # A15: 搜索 ID 子串 (Django 会自动把数字 ID 转成字符串来比对)
            Q(id__icontains=search_query) |
            # 额外赠送: 搜索品牌
            Q(brand__icontains=search_query)
        )

    return render(request, 'vendor_products.html', {
        'products': products,
        'search_query': search_query # 把搜索词传回去，为了保留在搜索框里
    })

@login_required
def vendor_add_product(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    if request.method == 'POST':
        product_name = request.POST.get('product_name')
        price = request.POST.get('price')
        brand = request.POST.get('brand')
        materials = request.POST.get('materials')
        description = request.POST.get('description')

        # ✨✨✨ 获取库存 ✨✨✨
        try:
            stock = int(request.POST.get('stock', 0))
        except ValueError:
            stock = 0

        # 获取用户想要的上架状态
        is_available = request.POST.get('available') == 'on'

        # ✨✨✨ 核心逻辑：如果库存 <= 0，强制下架 ✨✨✨
        if stock <= 0:
            is_available = False # 强制变不可见
            stock = 0 # 防止填负数

        # 1. 获取分类 ID
        category_id = request.POST.get('category')

        # ✨✨✨【修复步骤1】先找到 Category 对象 ✨✨✨
        category_obj = None
        if category_id:
            try:
                category_obj = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                pass

        tags_input = request.POST.get('tags')

        # ✨✨✨【修复步骤2】在创建时直接赋值 (category=category_obj) ✨✨✨
        product = Product.objects.create(
            user=request.user,
            product_name=product_name,
            price=price,
            brand=brand,
            materials=materials,
            description=description,
            stock=stock,        # 保存库存
            available=is_available, # 保存计算后的上架状态
            category=category_obj,  # 👈 重点：这里直接赋值！
        )

        if tags_input:
            tag_list = tags_input.split(',')
            for tag_name in tag_list:
                tag_name = tag_name.strip()
                if tag_name:
                    tag_obj, created = Tag.objects.get_or_create(tag_name=tag_name)
                    product.tags.add(tag_obj)

        # 处理图片 (保持不变)
        images = request.FILES.getlist('images')
        for i, image in enumerate(images):
            ProductImage.objects.create(product=product, image=image, display_order=i)

        # 处理视频 (如果有)
        if 'video' in request.FILES:
            product.video = request.FILES['video']
            product.save()

        return redirect('vendor_products')

    # GET 请求
    categories = Category.objects.all()
    return render(request, 'vendor_add_product.html', {
        'categories': categories
    })


@login_required
def toggle_product_availability(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    # ✅ 修改后 (只要是 Vendor 都能改):
    product = get_object_or_404(Product, id=product_id)

    # ✨✨✨ 增加保护逻辑：如果库存为0，不允许通过这个快捷按钮上架 ✨✨✨
    if product.stock <= 0 and not product.available:
        # 如果当前是下架状态，且库存为0，尝试上架时直接无视，或者 redirect 回去
        # 这里我们选择直接无视，保持 available = False
        pass
    else:
        # 正常切换
        product.available = not product.available
        product.save()

    return redirect('vendor_products')

@login_required
def vendor_orders(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    # ✅ 修改后 (看全店订单):
    orders = Order.objects.all().order_by('-order_date')

    return render(request, 'vendor_orders.html', {'orders': orders})


@login_required
def vendor_delete_product(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    # ✅ 修改后:
    product = get_object_or_404(Product, id=product_id)

    product.delete()

    return redirect('vendor_products')

@login_required
def vendor_edit_product(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    # ✅ 修改后:
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product.product_name = request.POST.get('product_name')
        product.price = request.POST.get('price')
        product.brand = request.POST.get('brand')
        product.materials = request.POST.get('materials')
        product.description = request.POST.get('description')

        # ✨✨✨ 获取库存并更新 ✨✨✨
        try:
            new_stock = int(request.POST.get('stock', 0))
        except ValueError:
            new_stock = 0
        product.stock = new_stock

        # 获取商家想要的上架状态
        user_wants_available = request.POST.get('available') == 'on'

        # ✨✨✨ 核心逻辑：库存为 0，自动覆盖为下架 ✨✨✨
        if product.stock <= 0:
            product.available = False
            product.stock = 0 # 修正负数
        else:
            product.available = user_wants_available # 库存充足时，听商家的

        if 'video' in request.FILES:
            product.video = request.FILES['video']

        # === 修复 Category 单选逻辑 ===
        category_id = request.POST.get('category')
        if category_id:
            try:
                product.category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                product.category = None # 或者保持原样，看你们需求
        # ============================

        # === Tags 逻辑保持不变 ===
        tags_input = request.POST.get('tags')
        if tags_input:
            product.tags.clear()
            tag_list = tags_input.split(',')
            for tag_name in tag_list:
                tag_name = tag_name.strip()
                if tag_name:
                    tag_obj, created = Tag.objects.get_or_create(tag_name=tag_name)
                    product.tags.add(tag_obj)

        # === 图片追加逻辑保持不变 ===
        new_images = request.FILES.getlist('new_images')
        for image in new_images:
            ProductImage.objects.create(product=product, image=image)

        product.save() # 记得最后 save 一下

        return redirect('vendor_products')

    categories = Category.objects.all()
    existing_tags = ", ".join([t.tag_name for t in product.tags.all()])

    return render(request, 'vendor_edit_product.html', {
        'product': product,
        'categories': categories,
        'existing_tags': existing_tags
    })

@login_required
def delete_product_image(request, image_id):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    image = get_object_or_404(ProductImage, id=image_id)


    product_id = image.product.id
    image.delete()
    return redirect('vendor_edit_product', product_id=product_id)