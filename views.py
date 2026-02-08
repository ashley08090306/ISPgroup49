from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from core.models import User
from .models import ShippingAddress, Product, Category, Tag, Order, ProductImage, ShopProfile, Review, ReviewMedia, Cart, CartItem
from django.db.models import Sum, Q, F, Avg, Min, Max
from django.contrib.auth import authenticate
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.db import OperationalError
import json, re # ✨ 必须导入 re 模块用于正则匹配
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone

# ==================== 首页与搜索 ====================

def home(request):
    base_qs = Product.objects.filter(available=True, stock__gt=0)

    # ✨✨✨ 恢复高级搜索逻辑 (Universal Dynamic Search) ✨✨✨
    search_query = request.GET.get('q', '').strip()

    if search_query:
        keywords = search_query.split()
        query_filter = Q()

        for keyword in keywords:
            # 预处理：去掉标签的 # 号，获取长度
            tag_keyword = keyword.lstrip('#')
            k_len = len(keyword)

            # 1. 判断是否包含中文/日文 (CJK 字符)
            is_cjk = bool(re.search(r'[\u4e00-\u9fa5\u3040-\u30ff]', keyword))

            # 初始化本次循环的查询
            or_lookup = Q()

            if is_cjk:
                # 🌏【亚洲语言模式】(无空格，信息密度高)
                if k_len == 1:
                    # 单字策略：严格。不搜描述和材质细节，防止"金"匹配到"金属扣"
                    or_lookup = (
                        Q(product_name__icontains=keyword) |
                        Q(brand__icontains=keyword) |
                        Q(category__category_name__icontains=keyword) |
                        Q(tags__tag_name__icontains=tag_keyword)
                    )
                else:
                    # 多字策略：宽松。全搜
                    or_lookup = (
                        Q(product_name__icontains=keyword) |
                        Q(brand__icontains=keyword) |
                        Q(category__category_name__icontains=keyword) |
                        Q(description__icontains=keyword) |
                        Q(materials__icontains=keyword) |
                        Q(tags__tag_name__icontains=tag_keyword)
                    )
            else:
                # 🌍【拉丁语言模式】(有空格，需单词边界 \b)
                # re.escape 确保用户输入 + * ? 等符号时不报错
                pattern = r'\b' + re.escape(keyword)

                if k_len <= 2:
                    # 极短词策略 (如 "Ho", "Co")：极严。只搜产品名。
                    # 防止 "Co" 匹配 "Tiffany & Co." 或 "Cotton"
                    or_lookup = Q(product_name__iregex=pattern)

                elif k_len < 5:
                    # 短词策略 (如 "Ring", "Gold")：中等。
                    # 搜重要字段，跳过 Description (描述文字太多容易误判)
                    or_lookup = (
                        Q(product_name__iregex=pattern) |
                        Q(brand__iregex=pattern) |
                        Q(category__category_name__iregex=pattern) |
                        Q(materials__iregex=pattern) |
                        Q(tags__tag_name__icontains=tag_keyword) # Tag 保持模糊匹配即可
                    )
                else:
                    # 长词策略 (如 "Diamond")：宽松。全搜。
                    or_lookup = (
                        Q(product_name__iregex=pattern) |
                        Q(brand__iregex=pattern) |
                        Q(category__category_name__iregex=pattern) |
                        Q(description__iregex=pattern) |
                        Q(materials__iregex=pattern) |
                        Q(tags__tag_name__icontains=tag_keyword)
                    )

            # AND 逻辑：必须同时满足所有关键词
            query_filter &= or_lookup

        # 应用筛选并去重
        base_qs = base_qs.filter(query_filter).distinct()

    # --- 以下逻辑保持不变 ---

    category_id = request.GET.get('category')
    current_category = None
    if category_id:
        try:
            current_category = Category.objects.get(id=category_id)
            base_qs = base_qs.filter(category=current_category)
        except Category.DoesNotExist:
            pass

    price_agg = base_qs.aggregate(min_p=Min('price'), max_p=Max('price'))
    global_min_price = int(price_agg['min_p'] or 0)
    global_max_price = int(price_agg['max_p'] or 10000)

    products_json_data = [
        {'id': p['id'], 'brand': p['brand'], 'price': float(p['price'])}
        for p in base_qs.values('id', 'brand', 'price')
    ]

    products = base_qs
    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        products = products.filter(brand__in=selected_brands)

    min_price_input = request.GET.get('min_price')
    max_price_input = request.GET.get('max_price')

    if min_price_input:
        try:
            products = products.filter(price__gte=float(min_price_input))
        except ValueError:
            pass

    if max_price_input:
        try:
            products = products.filter(price__lte=float(max_price_input))
        except ValueError:
            pass

    sort_by = request.GET.get('sort', 'novelty')
    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    else:
        products = products.order_by('-id')

    filter_brands = [
        "Louis Vuitton", "Dior", "YSL", "Van Cleef & Arpels", "Cartier",
        "Bulgari", "Chanel", "Tiffany & Co.", "Pandora", "Burberry", "Victoria Beckham"
    ]

    categories = Category.objects.all()

    is_filtering = bool(search_query or selected_brands or min_price_input or max_price_input)
    show_hero = not is_filtering and not category_id

    hero_slides = []
    if show_hero:
        hero_slides = [
            {'image': 'https://pbs.twimg.com/media/GrXpo4eXoAAQtE9?format=jpg&name=large', 'subtitle': 'The Campaign', 'title': 'BLOSSOM<br>GRACE', 'filter': 'brightness(0.8)'},
            {'image': 'https://www.essence.com/wp-content/uploads/2025/05/Untitled-design-2025-05-23T102343.012-1920x1080.png', 'subtitle': 'Haute Joaillerie', 'title': 'EVENING<br>ELEGANCE', 'filter': 'brightness(0.7)'},
            {'image': 'https://images.hdqwalls.com/wallpapers/jenna-ortega-dior-2023-x5.jpg', 'subtitle': 'Iconic Style', 'title': 'MODERN<br>MUSE', 'filter': 'brightness(0.8)'},
            {'image': 'https://www.chanel.com/puls-img/c_limit,w_3200/q_auto:good,dpr_auto,f_auto/1764081681922-one-hpjoa-d-majorpush-5760x1800px_1800x5760.jpg', 'subtitle': 'Radiance', 'title': 'GOLDEN<br>DETAILS', 'filter': 'brightness(0.8)'}
        ]

    context = {
        'products': products,
        'categories': categories,
        'search_query': search_query,
        'current_category': current_category,
        'show_hero': show_hero,
        'hero_slides': hero_slides,
        'filter_brands': filter_brands,
        'selected_brands': selected_brands,
        'global_min_price': global_min_price,
        'global_max_price': global_max_price,
        'current_min_price': min_price_input if min_price_input else global_min_price,
        'current_max_price': max_price_input if max_price_input else global_max_price,
        'current_sort': sort_by,
        'products_json': json.dumps(products_json_data),
    }
    return render(request, 'home.html', context)

# ==================== 用户个人中心 (User Profile) ====================

@login_required
def user_profile(request):
    # Vendor should not access user profile, redirect to dashboard
    if getattr(request.user, 'role', '') == 'vendor':
        return redirect('vendor_dashboard')

    active_tab = request.GET.get('tab', 'profile')
    user = request.user
    context = {'active_tab': active_tab}

    if active_tab == 'profile':
        if 'password_form' not in context:
            context['password_form'] = PasswordChangeForm(user)

    elif active_tab == 'address':
        context['addresses'] = ShippingAddress.objects.filter(user=user).order_by('-is_default', 'id')

    elif active_tab == 'orders':
        order_id = request.GET.get('order_id')
        if order_id:
            order_obj = get_object_or_404(Order, id=order_id, user=user)
            order_obj.total_price = order_obj.product.price * order_obj.quantity

            shipping_addr = ShippingAddress.objects.filter(user=user, is_default=True).first()
            if not shipping_addr:
                shipping_addr = ShippingAddress.objects.filter(user=user).first()

            context['order_detail'] = order_obj
            context['shipping_address'] = shipping_addr
        else:
            # ✨ New Filtering & Pagination Logic ✨
            orders_qs = Order.objects.filter(user=user)

            # 1. Filter by Status
            status_filter = request.GET.get('status', 'all')
            if status_filter != 'all':
                # Case-insensitive match for status
                orders_qs = orders_qs.filter(status__iexact=status_filter)

            # 2. Sort by Date
            sort_by = request.GET.get('sort', 'newest')
            if sort_by == 'oldest':
                orders_qs = orders_qs.order_by('order_date')
            else:
                orders_qs = orders_qs.order_by('-order_date')

            # 3. Total Count
            total_orders_count = orders_qs.count()

            # 4. Pagination (5 items per page)
            paginator = Paginator(orders_qs, 5)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)

            # Calculate total price for display
            for o in page_obj:
                o.total_price = o.product.price * o.quantity

            # Pagination Range Logic
            if hasattr(paginator, 'get_elided_page_range'):
                custom_page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
            else:
                custom_page_range = paginator.page_range

            context['orders'] = page_obj
            context['total_orders_count'] = total_orders_count
            context['current_status'] = status_filter
            context['current_sort'] = sort_by
            context['custom_page_range'] = custom_page_range

    elif active_tab == 'bag':
        cart_items = []
        cart_total = 0

        # ✨ DB Cart Logic for Profile ✨
        try:
            cart = Cart.objects.get(user=user)
            items = cart.items.select_related('product').all()
            for item in items:
                item.product.quantity = item.quantity
                item.product.total_price = item.product.price * item.quantity
                cart_total += item.product.total_price
                cart_items.append(item.product)
        except Cart.DoesNotExist:
            pass # No cart yet

        context['cart_items'] = cart_items
        context['cart_total'] = cart_total

    elif active_tab == 'reviews':
        reviews = Review.objects.filter(user=user).select_related('product').order_by('-created_at')
        context['reviews'] = reviews

    return render(request, 'user_profile.html', context)

@login_required
def update_profile_info(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        birth_date = request.POST.get('birth_date')
        if birth_date: user.birth_date = birth_date
        else: user.birth_date = None
        user.gender = request.POST.get('gender')
        user.save()
        messages.success(request, 'Profile updated successfully.')
    return redirect(f"{reverse('user_profile')}?tab=profile")

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect(f"{reverse('user_profile')}?tab=profile")
        else:
            return render(request, 'user_profile.html', {'active_tab': 'profile', 'password_form': form})
    return redirect(f"{reverse('user_profile')}?tab=profile")

@login_required
def add_address(request):
    if request.method == 'POST':
        category = request.POST.get('category')
        if category in ['home', 'office', 'school']:
            if ShippingAddress.objects.filter(user=request.user, category=category).exists():
                messages.error(request, f'You can only add one {category.capitalize()} address.')
                return redirect(f"{reverse('user_profile')}?tab=address")

        ShippingAddress.objects.create(
            user=request.user,
            country=request.POST.get('country'),
            city=request.POST.get('city'),
            district=request.POST.get('district'),
            street=request.POST.get('street'),
            detail_address=request.POST.get('detail_address'),
            category=category,
            is_default=False
        )
        messages.success(request, 'Address added successfully.')
    return redirect(f"{reverse('user_profile')}?tab=address")

@login_required
def delete_address(request, address_id):
    address = get_object_or_404(ShippingAddress, id=address_id, user=request.user)
    address.delete()
    messages.success(request, 'Address deleted.')
    return redirect(f"{reverse('user_profile')}?tab=address")

@login_required
def update_address(request, address_id):
    address = get_object_or_404(ShippingAddress, id=address_id, user=request.user)
    if request.method == 'POST':
        new_category = request.POST.get('category')
        if new_category != address.category and new_category in ['home', 'office', 'school']:
             if ShippingAddress.objects.filter(user=request.user, category=new_category).exclude(id=address_id).exists():
                messages.error(request, f'You already have a {new_category.capitalize()} address.')
                return redirect(f"{reverse('user_profile')}?tab=address")

        address.country = request.POST.get('country')
        address.city = request.POST.get('city')
        address.district = request.POST.get('district')
        address.street = request.POST.get('street')
        address.detail_address = request.POST.get('detail_address')
        address.category = new_category
        address.save()
        messages.success(request, 'Address updated.')
    return redirect(f"{reverse('user_profile')}?tab=address")

@login_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, user=request.user)
    review.delete()
    messages.success(request, 'Review deleted.')
    return redirect(f"{reverse('user_profile')}?tab=reviews")

# ==================== 商品详情与评论 ====================

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    error_message = None

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")

        if getattr(request.user, 'role', '') == 'vendor':
             error_message = "Vendors cannot write reviews."
        else:
            rating_val = request.POST.get('rating')
            comment_val = request.POST.get('comment')

            if rating_val and comment_val:
                try:
                    rating_int = int(rating_val)
                    new_review = Review.objects.create(
                        product=product,
                        user=request.user,
                        rating=rating_int,
                        comment=comment_val
                    )
                    try:
                        images = request.FILES.getlist('review_images')
                        for img in images:
                            ReviewMedia.objects.create(review=new_review, file=img, media_type='image')
                        video = request.FILES.get('review_video')
                        if video:
                            ReviewMedia.objects.create(review=new_review, file=video, media_type='video')
                    except Exception as media_e:
                        print(f"Media Upload Warning: {media_e}")
                    return redirect('product_detail', product_id=product.id)

                except OperationalError as e:
                    if "no such column" in str(e):
                        error_message = "System Update Required: Please run 'python manage.py migrate' in the console."
                    else:
                        error_message = f"Database Error: {str(e)}"
                except Exception as e:
                    error_message = f"Error: {str(e)}"
            else:
                error_message = "Please provide both a rating and a comment."

    try:
        reviews_qs = Review.objects.filter(product=product).order_by('-created_at')
        total_reviews = reviews_qs.count()
        avg_rating_data = reviews_qs.aggregate(Avg('rating'))
        avg_rating = round(avg_rating_data['rating__avg'] or 0, 1)

        distribution = []
        for star in range(5, 0, -1):
            count = reviews_qs.filter(rating=star).count()
            percent = (count / total_reviews * 100) if total_reviews > 0 else 0
            distribution.append({'star': star, 'percent': percent, 'count': count})

        reviews_list = []
        for r in reviews_qs:
            r.filled_stars = [1] * r.rating
            r.empty_stars = [1] * (5 - r.rating)
            reviews_list.append(r)

    except OperationalError as e:
        if "no such column" in str(e):
            error_message = "System Update Required: Please run 'python manage.py migrate' in the console."
        else:
            error_message = f"Database Error: {str(e)}"
        reviews_list = []
        total_reviews = 0
        avg_rating = 0
        distribution = []
    except Exception as db_e:
        error_message = f"Database Error: {str(db_e)}"
        reviews_list = []
        total_reviews = 0
        avg_rating = 0
        distribution = []

    context = {
        'product': product,
        'related_products': related_products,
        'reviews': reviews_list,
        'total_reviews': total_reviews,
        'avg_rating': avg_rating,
        'distribution': distribution,
        'error': error_message,
    }
    return render(request, 'product_detail.html', context)

def all_reviews(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    reviews_qs = Review.objects.filter(product=product).order_by('-created_at')

    total_reviews = reviews_qs.count()
    avg_rating_data = reviews_qs.aggregate(Avg('rating'))
    avg_rating = round(avg_rating_data['rating__avg'] or 0, 1)

    distribution = []
    for star in range(5, 0, -1):
        count = reviews_qs.filter(rating=star).count()
        percent = (count / total_reviews * 100) if total_reviews > 0 else 0
        distribution.append({'star': star, 'percent': percent, 'count': count})

    reviews_list = []
    for r in reviews_qs:
        r.filled_stars = [1] * r.rating
        r.empty_stars = [1] * (5 - r.rating)
        reviews_list.append(r)

    context = {
        'product': product,
        'reviews': reviews_list,
        'total_reviews': total_reviews,
        'avg_rating': avg_rating,
        'distribution': distribution,
    }
    return render(request, 'all_reviews.html', context)

# ==================== 购物车系统 (Persistent Updated) ====================

def add_to_cart(request):
    if request.method == 'POST':
        if request.user.is_authenticated and getattr(request.user, 'role', '') == 'vendor':
            return JsonResponse({'status': 'error', 'message': 'Vendors cannot purchase items.'}, status=403)

        product_id = request.POST.get('product_id')
        if not product_id: return JsonResponse({'status': 'error', 'message': 'Invalid product'}, status=400)

        # ✨ PERSISTENT LOGIC ✨
        if request.user.is_authenticated:
            # Use Database Cart
            try:
                product = Product.objects.get(id=product_id)
                cart, _ = Cart.objects.get_or_create(user=request.user)
                cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
                if not created:
                    cart_item.quantity += 1
                    cart_item.save()

                # Calculate total items
                total_items = cart.items.aggregate(total=Sum('quantity'))['total'] or 0
                return JsonResponse({'status': 'success', 'total_items': total_items})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        else:
            # Use Session Cart (Anonymous)
            cart = request.session.get('cart', {})
            if product_id in cart: cart[product_id] += 1
            else: cart[product_id] = 1
            request.session['cart'] = cart
            request.session.modified = True
            return JsonResponse({'status': 'success', 'total_items': sum(cart.values())})

    return JsonResponse({'status': 'error'}, status=400)

def cart_view(request):
    cart_items = []
    total_price = 0 # Calculate total for the view

    if request.user.is_authenticated:
        # ✨ DB Cart View ✨
        try:
            cart = Cart.objects.get(user=request.user)
            items = cart.items.select_related('product').all()
            for item in items:
                # Mock properties to match template expectation
                item.product.quantity = item.quantity
                item.product.total_price = item.product.price * item.quantity
                total_price += item.product.total_price
                cart_items.append(item.product)
        except Cart.DoesNotExist:
            pass # Empty cart
    else:
        # Session Cart View
        cart = request.session.get('cart', {})
        if cart:
            products = Product.objects.filter(id__in=cart.keys())
            for product in products:
                quantity = cart.get(str(product.id))
                if quantity:
                    product.quantity = quantity
                    product.total_price = product.price * quantity
                    total_price += product.total_price
                    cart_items.append(product)

    cart_items.sort(key=lambda x: x.id)
    return render(request, 'cart.html', {'cart_items': cart_items, 'total': total_price})

def update_cart(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = str(data.get('product_id'))
        action = data.get('action')

        if request.user.is_authenticated:
            # ✨ DB Cart Update ✨
            try:
                cart = Cart.objects.get(user=request.user)
                item = CartItem.objects.get(cart=cart, product_id=product_id)

                if action == 'increase':
                    item.quantity += 1
                    item.save()
                elif action == 'decrease':
                    item.quantity -= 1
                    if item.quantity <= 0: item.delete()
                    else: item.save()
                elif action == 'remove':
                    item.delete()

                return JsonResponse({'status': 'success'})
            except (Cart.DoesNotExist, CartItem.DoesNotExist):
                return JsonResponse({'status': 'error'}, status=400)
        else:
            # Session Cart Update
            cart = request.session.get('cart', {})
            if product_id in cart:
                if action == 'increase': cart[product_id] += 1
                elif action == 'decrease':
                    cart[product_id] -= 1
                    if cart[product_id] <= 0: del cart[product_id]
                elif action == 'remove': del cart[product_id]
                request.session['cart'] = cart
                request.session.modified = True
                return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)

# ==================== 认证系统 ====================

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        role = 'customer'
        country = request.POST.get('country')
        city = request.POST.get('city')
        district = request.POST.get('district')
        street = request.POST.get('street')
        detail = request.POST.get('detail_address')

        if password != confirm_password:
            return render(request, 'register.html', {'error': 'Passwords do not match!'})
        if not (country and city and street and detail):
            return render(request, 'register.html', {'error': 'Please provide a complete address.'})

        try:
            if User.objects.filter(username=username).exists():
                return render(request, 'register.html', {'error': f'Username "{username}" taken.'})
            if User.objects.filter(email=email).exists():
                return render(request, 'register.html', {'error': 'Email already registered.'})

            user = User.objects.create_user(username=username, email=email, password=password, role=role)
            ShippingAddress.objects.create(user=user, country=country, city=city, district=district, street=street, detail_address=detail, category='home', is_default=True)
            user.backend = 'core.authentication.EmailOrUsernameBackend'

            # Auto login
            login(request, user)

            # ✨ MERGE SESSION CART ON REGISTER ✨
            session_cart = request.session.get('cart', {})
            if session_cart:
                cart, _ = Cart.objects.get_or_create(user=user)
                for pid, qty in session_cart.items():
                    item, created = CartItem.objects.get_or_create(cart=cart, product_id=pid)
                    if created: item.quantity = qty
                    else: item.quantity += qty
                    item.save()
                request.session['cart'] = {}

            return redirect('home')
        except Exception as e:
            return render(request, 'register.html', {'error': 'Something went wrong.'})
    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        data = request.POST.copy()
        user = authenticate(request, username=data.get('username'), password=data.get('password'))
        if user is not None:
            login(request, user)

            # ✨ MERGE SESSION CART TO DB CART ON LOGIN ✨
            session_cart = request.session.get('cart', {})
            if session_cart:
                # Ensure user has a cart
                cart, _ = Cart.objects.get_or_create(user=user)

                # Merge items
                for pid, qty in session_cart.items():
                    try:
                        # Check if product still exists
                        if Product.objects.filter(id=pid).exists():
                            item, created = CartItem.objects.get_or_create(cart=cart, product_id=pid)
                            if created:
                                item.quantity = qty
                            else:
                                item.quantity += qty
                            item.save()
                    except Exception:
                        continue

                # Clear session cart after merge
                request.session['cart'] = {}
                request.session.modified = True

            if getattr(user, 'role', '') == 'vendor': return redirect('vendor_dashboard')
            return redirect(request.GET.get('next') or 'home')
        else:
            return render(request, 'login.html', {'form': AuthenticationForm(data=data), 'error': 'Invalid credentials.'})
    return render(request, 'login.html', {'form': AuthenticationForm()})

def logout_view(request):
    logout(request)
    return redirect('home')

# ==================== 商家视图 (Vendor Portal) ====================

@login_required
def vendor_dashboard(request):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
    total_sales = Order.objects.aggregate(total=Sum(F('product__price') * F('quantity')))['total']
    active_products = Product.objects.filter(available=True).count()
    pending_orders = Order.objects.filter(status='Pending').count()
    all_orders = Order.objects.all()
    return render(request, 'vendor_dashboard.html', {
        'total_sales': total_sales or 0, 'active_products': active_products,
        'pending_orders': pending_orders, 'orders': all_orders
    })

@login_required
def vendor_myshop(request):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
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
    return render(request, 'vendor_myshop.html', {'shop': shop})

@login_required
def vendor_products(request):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
    products = Product.objects.all().order_by('-id')
    search_query = request.GET.get('q')
    if search_query:
        products = products.filter(Q(product_name__icontains=search_query) | Q(id__icontains=search_query) | Q(brand__icontains=search_query))
    paginator = Paginator(products, 5)
    page_obj = paginator.get_page(request.GET.get('page'))
    custom_page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1) if hasattr(paginator, 'get_elided_page_range') else paginator.page_range
    return render(request, 'vendor_products.html', {'products': page_obj, 'search_query': search_query, 'custom_page_range': custom_page_range})

@login_required
def vendor_add_product(request):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
    if request.method == 'POST':
        product = Product.objects.create(
            user=request.user,
            product_name=request.POST.get('product_name'),
            price=request.POST.get('price'),
            brand=request.POST.get('brand'),
            materials=request.POST.get('materials'),
            description=request.POST.get('description'),
            stock=int(request.POST.get('stock', 0)),
            available=request.POST.get('available') == 'on',
            category_id=request.POST.get('category')
        )
        if request.POST.get('tags'):
            for tag_name in request.POST.get('tags').split(','):
                if tag_name.strip():
                    tag_obj, _ = Tag.objects.get_or_create(tag_name=tag_name.strip())
                    product.tags.add(tag_obj)
        for i, image in enumerate(request.FILES.getlist('images')):
            ProductImage.objects.create(product=product, image=image, display_order=i)
        if 'video' in request.FILES:
            product.video = request.FILES['video']
            product.save()
        return redirect('vendor_products')
    return render(request, 'vendor_add_product.html', {'categories': Category.objects.all()})

@login_required
def toggle_product_availability(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
    product = get_object_or_404(Product, id=product_id)
    if product.stock > 0:
        product.available = not product.available
        product.save()
    return redirect('vendor_products')

@login_required
def vendor_orders(request):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
    orders = Order.objects.all().order_by('-order_date')
    paginator = Paginator(orders, 8)
    page_obj = paginator.get_page(request.GET.get('page'))
    custom_page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1) if hasattr(paginator, 'get_elided_page_range') else paginator.page_range
    return render(request, 'vendor_orders.html', {'orders': page_obj, 'custom_page_range': custom_page_range})

@login_required
def vendor_delete_product(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
    get_object_or_404(Product, id=product_id).delete()
    return redirect('vendor_products')

@login_required
def vendor_edit_product(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        product.product_name = request.POST.get('product_name')
        product.price = request.POST.get('price')
        product.brand = request.POST.get('brand')
        product.materials = request.POST.get('materials')
        product.description = request.POST.get('description')
        product.stock = int(request.POST.get('stock', 0))
        product.available = (request.POST.get('available') == 'on') if product.stock > 0 else False
        if 'video' in request.FILES: product.video = request.FILES['video']
        if request.POST.get('category'): product.category_id = request.POST.get('category')
        if request.POST.get('tags'):
            product.tags.clear()
            for tag_name in request.POST.get('tags').split(','):
                if tag_name.strip():
                    tag_obj, _ = Tag.objects.get_or_create(tag_name=tag_name.strip())
                    product.tags.add(tag_obj)
        for image in request.FILES.getlist('new_images'):
            ProductImage.objects.create(product=product, image=image)
        product.save()
        return redirect('vendor_products')
    return render(request, 'vendor_edit_product.html', {'product': product, 'categories': Category.objects.all(), 'existing_tags': ", ".join([t.tag_name for t in product.tags.all()])})

@login_required
def delete_product_image(request, image_id):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
    image = get_object_or_404(ProductImage, id=image_id)
    pid = image.product.id
    image.delete()
    return redirect('vendor_edit_product', product_id=pid)

@login_required
def delete_product_video(request, product_id):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied
    product = get_object_or_404(Product, id=product_id)
    product.video.delete()
    product.save()
    return redirect('vendor_edit_product', product_id=product.id)

def heartbeat(request):
    if request.user.is_authenticated: request.session.modified = True
    return HttpResponse("alive")

@login_required
def checkout(request):
    # 1. Get Cart Items
    cart_items = []
    total_price = 0

    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            items = cart.items.select_related('product').all()
            for item in items:
                item.product.quantity = item.quantity
                item.product.total_price = item.product.price * item.quantity
                total_price += item.product.total_price
                cart_items.append(item.product)
        except Cart.DoesNotExist:
            pass
    else:
        # Fallback for session (should force login though per requirement)
        cart = request.session.get('cart', {})
        if cart:
            products = Product.objects.filter(id__in=cart.keys())
            for product in products:
                quantity = cart.get(str(product.id))
                if quantity:
                    total_price += product.price * quantity
                    product.quantity = quantity
                    cart_items.append(product)

    if not cart_items: return redirect('home')

    # 2. Get Saved Addresses
    saved_addresses = []
    if request.user.is_authenticated:
        saved_addresses = ShippingAddress.objects.filter(user=request.user).order_by('-is_default')

    # 3. Handle POST (Place Order)
    if request.method == 'POST':
        # ✨ SAFEGUARD: Only process order if 'payment_method' is present in POST data
        # This prevents the cart's accidental POST request from triggering an empty order
        if 'payment_method' in request.POST:
            order_ids = []

            # Determine address source
            address_source = request.POST.get('address_source', 'new')
            shipping_info = ""

            if address_source == 'existing':
                addr_id = request.POST.get('selected_address_id')
                # Add check if addr_id exists
                if addr_id:
                    addr = get_object_or_404(ShippingAddress, id=addr_id, user=request.user)
                    shipping_info = f"{addr.detail_address}, {addr.street}, {addr.city}, {addr.country}"
            else:
                # Create/Use new address (basic logic, typically we'd save it)
                shipping_info = f"{request.POST.get('address_detail')}, {request.POST.get('address_street')}, {request.POST.get('address_city')}"
                # Optionally save this new address to DB if user wants

            for item in cart_items:
                order = Order.objects.create(
                    user=request.user,
                    product=item,
                    quantity=item.quantity,
                    status="Pending"
                    # In real app, we'd save shipping_info to order
                )
                order_ids.append(order.id)
                item.stock -= item.quantity
                item.save()

            # Clear Cart
            if request.user.is_authenticated:
                Cart.objects.filter(user=request.user).delete()
            else:
                request.session['cart'] = {}

            return redirect('order_confirmation', order_id=order_ids[0])
        else:
            # If POST but no payment method (e.g. from old cart), fall through to render checkout page
            pass

    context = {
        'cart_items': cart_items,
        'total': total_price,
        'saved_addresses': saved_addresses
    }
    return render(request, 'checkout.html', context)

def order_confirmation(request, order_id):
    primary_order = get_object_or_404(Order, id=order_id, user=request.user)

    # Heuristic: Get orders created within 5 seconds of the primary order by the same user
    # This groups the cart items together for the receipt view
    time_threshold_before = primary_order.order_date - timezone.timedelta(seconds=5)
    time_threshold_after = primary_order.order_date + timezone.timedelta(seconds=5)

    order_items = Order.objects.filter(
        user=request.user,
        order_date__range=(time_threshold_before, time_threshold_after)
    )

    # Calculate totals
    for item in order_items:
        item.total_price = item.product.price * item.quantity

    total_amount = sum(item.total_price for item in order_items)

    context = {
        'order': primary_order, # For singular reference (ID, date)
        'order_items': order_items, # For list view
        'total_amount': total_amount
    }
    return render(request, 'order_confirmation.html', context)

@login_required
def order_process(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Security check: Ensure only vendors can access this
    if getattr(request.user, 'role', '') != 'vendor':
        raise PermissionDenied

    # ✨ Calculate total price for display
    order.total_price = order.product.price * order.quantity

    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = ['Pending', 'Shipped', 'Processed', 'Cancelled']

        if new_status in valid_statuses:
            order.status = new_status
            order.save()
            messages.success(request, f"Order #{order.id} status updated to {new_status}.")
        return redirect('order_process', order_id=order.id)

    return render(request, 'order_process.html', {'order': order})

# ✨✨✨ UPDATED VENDOR REVIEW MANAGEMENT (Fetching ALL reviews for demo purposes) ✨✨✨
@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status == 'Pending':
        order.status = 'Cancelled'
        order.save()
        messages.success(request, f"Order #{order.id} has been cancelled successfully.")
    else:
        messages.error(request, "This order cannot be cancelled at this stage.")

    return redirect('/profile/?tab=orders')

@login_required
def vendor_reviews(request):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied

    # Base Query: Fetch all reviews (using demo logic as requested)
    reviews = Review.objects.all().select_related('product', 'user')

    # 1. Product ID Filter
    product_id = request.GET.get('product_id', '').strip()
    if product_id:
        reviews = reviews.filter(product__id=product_id)

    # 2. Reply Status Filter
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'replied':
        # Show only replied reviews (vendor_reply is not empty)
        reviews = reviews.exclude(Q(vendor_reply__isnull=True) | Q(vendor_reply=''))
    elif status_filter == 'unreplied':
        # Show only unreplied reviews
        reviews = reviews.filter(Q(vendor_reply__isnull=True) | Q(vendor_reply=''))

    # 3. Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'rating_desc':
        reviews = reviews.order_by('-rating')
    elif sort_by == 'rating_asc':
        reviews = reviews.order_by('rating')
    else: # Default: Newest
        reviews = reviews.order_by('-created_at')

    # Get total count after filtering for UI
    total_reviews_count = reviews.count()

    # ✨ CHANGED: 5 items per page
    paginator = Paginator(reviews, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ✨ NEW: Smart pagination range (e.g., 1 2 ... 5 6 7 ... 10)
    if hasattr(paginator, 'get_elided_page_range'):
        custom_page_range = paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
    else:
        custom_page_range = paginator.page_range

    context = {
        'reviews': page_obj,
        'total_reviews_count': total_reviews_count,
        # Pass filters back to context to keep inputs populated
        'current_product_id': product_id,
        'current_status': status_filter,
        'current_sort': sort_by,
        'custom_page_range': custom_page_range, # Pass the range to template
    }

    return render(request, 'vendor_reviews.html', context)

@login_required
def vendor_reply_review(request, review_id):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied

    review = get_object_or_404(Review, id=review_id)

    # 🚨 RELAXED CHECK: Allowing reply even if product owner doesn't match login
    # to support the demo scenario.
    # if review.product.user != request.user: raise PermissionDenied

    if request.method == 'POST':
        reply_text = request.POST.get('reply_text')
        if reply_text:
            review.vendor_reply = reply_text
            review.replied_at = timezone.now()
            review.save()
            messages.success(request, 'Reply posted successfully.')

    return redirect('vendor_reviews')