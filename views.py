from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from core.models import User  # 确保导入的是自定义的 User 模型
from .models import ShippingAddress, Product, Category, Tag, Order, ProductImage, ShopProfile
from django.db.models import Sum, Q, F, Avg
from django.contrib.auth import authenticate
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
import json


# ==================== 公共视图 ====================

def home(request):
    # 【注意】这里不要加 Vendor 重定向逻辑，否则 View Shop 会死循环
    # Vendor 访问这里就是为了看前台效果 (Customer View)

    # 1. 获取基础数据
    categories = Category.objects.all()
    products = Product.objects.filter(available=True, stock__gt=0).order_by('-id')

    # 2. 处理搜索 (Search)
    search_query = request.GET.get('q')
    if search_query:
        products = products.filter(
            Q(product_name__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # 3. 处理分类过滤 (Category Filter)
    category_id = request.GET.get('category')
    current_category = None
    if category_id:
        try:
            current_category = Category.objects.get(id=category_id)
            products = products.filter(category=current_category)
        except Category.DoesNotExist:
            pass

    # 4. 判断是否显示 Hero Banner
    show_hero = not search_query and not category_id

    # 5. 定义 Hero Carousel 数据
    hero_slides = []
    if show_hero:
        hero_slides = [
            {
                'image': 'https://pbs.twimg.com/media/GrXpo4eXoAAQtE9?format=jpg&name=large',
                'subtitle': 'The Campaign',
                'title': 'BLOSSOM<br>GRACE',
                'filter': 'brightness(0.8)'
            },
            {
                'image': 'https://www.essence.com/wp-content/uploads/2025/05/Untitled-design-2025-05-23T102343.012-1920x1080.png',
                'subtitle': 'Haute Joaillerie',
                'title': 'EVENING<br>ELEGANCE',
                'filter': 'brightness(0.7)'
            },
            {
                'image': 'https://images.hdqwalls.com/wallpapers/jenna-ortega-dior-2023-x5.jpg',
                'subtitle': 'Iconic Style',
                'title': 'MODERN<br>MUSE',
                'filter': 'brightness(0.8)'
            },
            {
                'image': 'https://www.chanel.com/puls-img/c_limit,w_3200/q_auto:good,dpr_auto,f_auto/1764081681922-one-hpjoa-d-majorpush-5760x1800px_1800x5760.jpg',
                'subtitle': 'Radiance',
                'title': 'GOLDEN<br>DETAILS',
                'filter': 'brightness(0.8)'
            }
        ]

    context = {
        'products': products,
        'categories': categories,
        'search_query': search_query,
        'current_category': current_category,
        'show_hero': show_hero,
        'hero_slides': hero_slides,
    }
    return render(request, 'home.html', context)

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # 获取相关产品
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]

    return render(request, 'product_detail.html', {
        'product': product,
        'related_products': related_products,
    })

# ==================== 购物车系统 (基于 Session) ====================

def add_to_cart(request):
    """
    AJAX 添加到购物车
    """
    if request.method == 'POST':
        # ✨✨✨【安全防护】如果是 Vendor，禁止添加到购物车 ✨✨✨
        if request.user.is_authenticated and getattr(request.user, 'role', '') == 'vendor':
            return JsonResponse({'status': 'error', 'message': 'Vendors cannot purchase items.'}, status=403)

        product_id = request.POST.get('product_id')

        if not product_id:
            return JsonResponse({'status': 'error', 'message': 'Invalid product'}, status=400)

        cart = request.session.get('cart', {})

        if product_id in cart:
            cart[product_id] += 1
        else:
            cart[product_id] = 1

        request.session['cart'] = cart
        request.session.modified = True

        total_items = sum(cart.values())

        return JsonResponse({'status': 'success', 'total_items': total_items})

    return JsonResponse({'status': 'error'}, status=400)

def cart_view(request):
    cart = request.session.get('cart', {})
    cart_items = []

    if cart:
        products = Product.objects.filter(id__in=cart.keys())
        for product in products:
            quantity = cart.get(str(product.id))
            if quantity:
                product.quantity = quantity
                product.total_price = product.price * quantity
                cart_items.append(product)

    cart_items.sort(key=lambda x: x.id)

    return render(request, 'cart.html', {'cart_items': cart_items})

def update_cart(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = str(data.get('product_id'))
        action = data.get('action')

        cart = request.session.get('cart', {})

        if product_id in cart:
            if action == 'increase':
                cart[product_id] += 1
            elif action == 'decrease':
                cart[product_id] -= 1
                if cart[product_id] <= 0:
                    del cart[product_id]
            elif action == 'remove':
                del cart[product_id]

            request.session['cart'] = cart
            request.session.modified = True

            return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)


# ==================== 用户认证系统 ====================

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role = request.POST.get('role')

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

                # 必须手动指定后端
                user.backend = 'core.authentication.EmailOrUsernameBackend'

                login(request, user)

                if role == 'vendor':
                    return redirect('vendor_dashboard')
                else:
                    return redirect('home')

            except Exception as e:
                print(f"Registration Error: {e}")
                return render(request, 'register.html', {'error': 'Something went wrong during registration. Please try again.'})

    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        data = request.POST.copy()
        login_input = data.get('username')
        password_input = data.get('password')

        user = authenticate(request, username=login_input, password=password_input)

        if user is not None:
            # 登录成功
            login(request, user)

            # ✨✨✨【重点修复：优先级调整】✨✨✨
            # 必须先把 Vendor 踢去 Dashboard，然后再去管 next 参数
            # 这样即使 Vendor 是从 Product Detail 页点击登录的，也会被强制转走
            if getattr(user, 'role', '') == 'vendor':
                return redirect('vendor_dashboard')

            # 如果不是 Vendor (即 Customer)，才检查 next 跳转
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)

            # 默认去首页
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

    total_sales_data = Order.objects.aggregate(total=Sum(F('product__price') * F('quantity')))
    total_sales = total_sales_data['total']

    active_products = Product.objects.filter(available=True).count()
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

    shop, created = ShopProfile.objects.get_or_create(id=1)

    if request.method == 'POST':
        shop.shop_name = request.POST.get('shop_name')
        shop.email = request.POST.get('email')
        shop.country = request.POST.get('country')
        shop.city = request.POST.get('city')
        shop.district = request.POST.get('district')
        shop.street = request.POST.get('street')
        shop.detail_address = request.POST.get('detail_address')
        shop.save()
        return redirect('vendor_myshop')

    context = {
        'shop': shop
    }
    return render(request, 'vendor_myshop.html', context)

@login_required
def vendor_products(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    products = Product.objects.all().order_by('-id')
    search_query = request.GET.get('q')

    if search_query:
        products = products.filter(
            Q(product_name__icontains=search_query) |
            Q(id__icontains=search_query) |
            Q(brand__icontains=search_query)
        )

    return render(request, 'vendor_products.html', {
        'products': products,
        'search_query': search_query
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

        try:
            stock = int(request.POST.get('stock', 0))
        except ValueError:
            stock = 0

        is_available = request.POST.get('available') == 'on'

        if stock <= 0:
            is_available = False
            stock = 0

        category_id = request.POST.get('category')
        category_obj = None
        if category_id:
            try:
                category_obj = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                pass

        tags_input = request.POST.get('tags')

        product = Product.objects.create(
            user=request.user,
            product_name=product_name,
            price=price,
            brand=brand,
            materials=materials,
            description=description,
            stock=stock,
            available=is_available,
            category=category_obj,
        )

        if tags_input:
            tag_list = tags_input.split(',')
            for tag_name in tag_list:
                tag_name = tag_name.strip()
                if tag_name:
                    tag_obj, created = Tag.objects.get_or_create(tag_name=tag_name)
                    product.tags.add(tag_obj)

        images = request.FILES.getlist('images')
        for i, image in enumerate(images):
            ProductImage.objects.create(product=product, image=image, display_order=i)

        if 'video' in request.FILES:
            product.video = request.FILES['video']
            product.save()

        return redirect('vendor_products')

    categories = Category.objects.all()
    return render(request, 'vendor_add_product.html', {
        'categories': categories
    })


@login_required
def toggle_product_availability(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    product = get_object_or_404(Product, id=product_id)

    if product.stock <= 0 and not product.available:
        pass
    else:
        product.available = not product.available
        product.save()

    return redirect('vendor_products')

@login_required
def vendor_orders(request):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    orders = Order.objects.all().order_by('-order_date')

    return render(request, 'vendor_orders.html', {'orders': orders})


@login_required
def vendor_delete_product(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return redirect('vendor_products')

@login_required
def vendor_edit_product(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor':
        return redirect('home')

    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product.product_name = request.POST.get('product_name')
        product.price = request.POST.get('price')
        product.brand = request.POST.get('brand')
        product.materials = request.POST.get('materials')
        product.description = request.POST.get('description')

        try:
            new_stock = int(request.POST.get('stock', 0))
        except ValueError:
            new_stock = 0
        product.stock = new_stock

        user_wants_available = request.POST.get('available') == 'on'

        if product.stock <= 0:
            product.available = False
            product.stock = 0
        else:
            product.available = user_wants_available

        if 'video' in request.FILES:
            product.video = request.FILES['video']

        category_id = request.POST.get('category')
        if category_id:
            try:
                product.category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                product.category = None

        tags_input = request.POST.get('tags')
        if tags_input:
            product.tags.clear()
            tag_list = tags_input.split(',')
            for tag_name in tag_list:
                tag_name = tag_name.strip()
                if tag_name:
                    tag_obj, created = Tag.objects.get_or_create(tag_name=tag_name)
                    product.tags.add(tag_obj)

        new_images = request.FILES.getlist('new_images')
        for image in new_images:
            ProductImage.objects.create(product=product, image=image)

        product.save()
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

def heartbeat(request):
    """
    心跳接口：仅用于保持 Session 活跃
    前端 JS 会每隔一段时间调用一次
    """
    if request.user.is_authenticated:
        request.session.modified = True # 强制刷新 Session 时间
    return HttpResponse("alive")