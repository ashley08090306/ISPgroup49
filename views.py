from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from core.models import User
# ✨ 核心修改：引入 OrderItem
from .models import ShippingAddress, Product, Category, Tag, Order, OrderItem, ProductImage, ShopProfile, Review, ReviewMedia, Cart, CartItem
from django.db.models import Sum, Q, F, Avg, Min, Max
from django.contrib.auth import authenticate
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.db import OperationalError
import json, re
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib import messages
from .utils import sensitive_filter
from django.utils import timezone # ✨ 核心修改：必须引入

# ==================== 首页与搜索 (多语言支持 + 停用词优化版) ====================

def home(request):
    base_qs = Product.objects.filter(available=True, stock__gt=0)

    # ✨✨✨ 获取搜索关键词 ✨✨✨
    search_query = request.GET.get('q', '').strip()

    # 🌟 NEW: 用于数据库查询的关键词
    search_query_for_db = search_query

    if search_query:
        # ==================== 核心修改1：智能翻译 ====================
        try:
            from deep_translator import GoogleTranslator
            # 自动检测 -> 翻译为英文
            search_query_for_db = GoogleTranslator(source='auto', target='en').translate(search_query)
            print(f"🌍 [Search] Input: '{search_query}' -> Translated: '{search_query_for_db}'")
        except Exception as e:
            print(f"⚠️ [Search Error] Translation failed: {e}")
            search_query_for_db = search_query

        # ==================== 核心修改2：去除无意义的冠词 (Stop Words) ====================
        # 解决 "太阳" -> "The sun" 导致搜索失败的问题
        # 我们只保留核心名词，去除 the, a, an 等
        stop_words = {'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for'}

        # 拆分关键词
        raw_keywords = search_query_for_db.split()

        # 过滤关键词：保留非停用词，或者如果是CJK字符(不用管停用词)
        keywords = []
        for k in raw_keywords:
            # 如果是纯英文且在停用词表中，跳过
            if re.match(r'^[a-zA-Z]+$', k) and k.lower() in stop_words:
                continue
            keywords.append(k)

        # 如果过滤完没词了(比如用户就搜了"The")，就回退到原始列表
        if not keywords:
            keywords = raw_keywords

        # ==================== 构建查询 ====================
        query_filter = Q()

        for keyword in keywords:
            tag_keyword = keyword.lstrip('#')
            k_len = len(keyword)

            # 判断是否为中日韩字符
            is_cjk = bool(re.search(r'[\u4e00-\u9fa5\u3040-\u30ff]', keyword))
            or_lookup = Q()

            if is_cjk:
                # CJK 宽泛匹配
                if k_len == 1:
                    or_lookup = (
                        Q(product_name__icontains=keyword) |
                        Q(brand__icontains=keyword) |
                        Q(category__category_name__icontains=keyword) |
                        Q(tags__tag_name__icontains=tag_keyword)
                    )
                else:
                    or_lookup = (
                        Q(product_name__icontains=keyword) |
                        Q(brand__icontains=keyword) |
                        Q(category__category_name__icontains=keyword) |
                        Q(description__icontains=keyword) |
                        Q(materials__icontains=keyword) |
                        Q(tags__tag_name__icontains=tag_keyword)
                    )
            else:
                # 英文匹配逻辑
                pattern = r'\b' + re.escape(keyword)

                if k_len <= 2:
                    # 极短词 (如 "Go")：严格匹配单词边界
                    or_lookup = Q(product_name__iregex=pattern)
                elif k_len < 5:
                    # 短词 (如 "Sun", "Ring")：匹配名字、品牌、分类、标签
                    # ✨ 修复：增加了 description 匹配，防止漏网之鱼，但在排序时产品名优先
                    or_lookup = (
                        Q(product_name__iregex=pattern) |
                        Q(brand__iregex=pattern) |
                        Q(category__category_name__iregex=pattern) |
                        Q(description__icontains=keyword) | # 放宽这里，允许匹配描述
                        Q(materials__iregex=pattern) |
                        Q(tags__tag_name__icontains=tag_keyword)
                    )
                else:
                    # 长词：全面宽泛匹配
                    or_lookup = (
                        Q(product_name__iregex=pattern) |
                        Q(brand__iregex=pattern) |
                        Q(category__category_name__iregex=pattern) |
                        Q(description__iregex=pattern) |
                        Q(materials__iregex=pattern) |
                        Q(tags__tag_name__icontains=tag_keyword)
                    )
            query_filter &= or_lookup
        base_qs = base_qs.filter(query_filter).distinct()

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

    # ✨✨✨ 核心修改：适配一单多品结构 ✨✨✨
    elif active_tab == 'orders':
        order_id = request.GET.get('order_id')
        if order_id:
            order_obj = get_object_or_404(Order, id=order_id, user=user)

            shipping_addr = ShippingAddress.objects.filter(user=user, is_default=True).first()
            if not shipping_addr:
                shipping_addr = ShippingAddress.objects.filter(user=user).first()

            context['order_detail'] = order_obj
            # 通过 items 反向查询所有子订单项
            context['order_items'] = order_obj.items.select_related('product').all()
            context['shipping_address'] = shipping_addr
        else:
            orders_qs = Order.objects.filter(user=user).prefetch_related('items__product').order_by('-order_date')

            status_filter = request.GET.get('status', 'all')
            if status_filter != 'all':
                orders_qs = orders_qs.filter(status__iexact=status_filter)

            sort_by = request.GET.get('sort', 'newest')
            if sort_by == 'oldest':
                orders_qs = orders_qs.order_by('order_date')
            else:
                orders_qs = orders_qs.order_by('-order_date')

            total_orders_count = orders_qs.count()

            paginator = Paginator(orders_qs, 5)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)

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
        try:
            cart = Cart.objects.get(user=user)
            items = cart.items.select_related('product').all()
            for item in items:
                item.product.quantity = item.quantity
                item.product.total_price = item.product.price * item.quantity
                cart_total += item.product.total_price
                cart_items.append(item.product)
        except Cart.DoesNotExist:
            pass

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
    related_products = (
        Product.objects.filter(category=product.category)
        .exclude(id=product.id)[:4]
    )

    # 状态变量：用于在前端 Modal 中保留用户的输入，防止被清空
    error_message = None
    submitted_rating = 5
    submitted_comment = ""
    has_error_modal = False

    # ✅ IMPORTANT: compute has_purchased for BOTH GET and POST
    has_purchased = False
    if request.user.is_authenticated:
        has_purchased = OrderItem.objects.filter(
            order__user=request.user,
            order__status='Processed',   # only "Processed" counts as purchased
            product=product
        ).exists()

    # Handle review submission (POST)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")

        if not has_purchased:
            messages.error(request, "Only customers who have purchased (Processed) can leave a review.")
            return redirect('product_detail', product_id=product.id)

        if getattr(request.user, 'role', '') == 'vendor':
             error_message = "Vendors cannot write reviews."
             has_error_modal = True
        else:
            rating_val = request.POST.get('rating')
            comment_val = request.POST.get('comment')

            if not rating_val or not comment_val:
                messages.error(request, "Please provide both a rating and a comment.")
                return redirect('product_detail', product_id=product.id)

            try:
                submitted_rating = int(rating_val)
                submitted_comment = comment_val

                # ✨✨✨ 敏感词拦截核心逻辑 ✨✨✨
                is_sensitive, filtered_text = sensitive_filter.filter(comment_val)

                if is_sensitive:
                    # 命中敏感词，不存入数据库，开启 Modal 保留输入状态
                    error_message = "Warning: Your review contains inappropriate language (such as profanity or sensitive topics). Please edit your comment before posting."
                    has_error_modal = True
                else:
                    # 正常保存
                    new_review = Review.objects.create(
                        product=product,
                        user=request.user,
                        rating=submitted_rating,
                        comment=comment_val
                    )

                    # Upload multiple images
                    images = request.FILES.getlist('review_images')
                    for img in images:
                        ReviewMedia.objects.create(
                            review=new_review,
                            file=img,
                            media_type='image'
                        )

                    # Upload max 1 video
                    video = request.FILES.get('review_video')
                    if video:
                        ReviewMedia.objects.create(
                            review=new_review,
                            file=video,
                            media_type='video'
                        )

                    messages.success(request, "Review submitted successfully!")
                    return redirect('product_detail', product_id=product.id)

            except ValueError:
                messages.error(request, "Invalid rating value.")
                return redirect('product_detail', product_id=product.id)
            except Exception as e:
                error_message = f"Failed to submit review: {e}"
                has_error_modal = True

    # ===== Reviews display data =====
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
        'related_products': related_products,
        'reviews': reviews_list,
        'total_reviews': total_reviews,
        'avg_rating': avg_rating,
        'distribution': distribution,
        'has_purchased': has_purchased,

        # ✨ 传回前端，用于展示红框警告并保留用户输入
        'error_message': error_message,
        'submitted_comment': submitted_comment,
        'submitted_rating': submitted_rating,
        'has_error_modal': has_error_modal,
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
            print(f"⚠️ Register Error: {e}")  # ✨ 把真正的错误原因打印在你的终端里
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
    # ✨ 核心修改：跨表计算总销售额 (OrderItem price * quantity)
    total_sales = Order.objects.aggregate(total=Sum(F('items__price') * F('items__quantity')))['total']
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

# ✨✨✨ 核心修改：Vendor Orders 列表显示总价 ✨✨✨
@login_required
def vendor_orders(request):
    if getattr(request.user, 'role', '') != 'vendor': raise PermissionDenied

    # 计算每个订单的总价并作为字段 'calculated_total' 返回
    orders = Order.objects.annotate(
        calculated_total=Sum(F('items__price') * F('items__quantity'))
    ).order_by('-order_date')

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

# ✨✨✨ 核心修改：Checkout 创建逻辑 (一单多品) ✨✨✨
@login_required
def checkout(request):
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

    saved_addresses = []
    if request.user.is_authenticated:
        saved_addresses = ShippingAddress.objects.filter(user=request.user).order_by('-is_default')

    if request.method == 'POST':
        if 'payment_method' in request.POST:
            # 1. 构造收货信息
            shipping_info = ""
            address_source = request.POST.get('address_source', 'new')
            if address_source == 'existing':
                addr_id = request.POST.get('selected_address_id')
                if addr_id:
                    addr = get_object_or_404(ShippingAddress, id=addr_id, user=request.user)
                    shipping_info = f"{addr.detail_address}, {addr.street}, {addr.city}, {addr.country}"
            else:
                shipping_info = f"{request.POST.get('address_detail')}, {request.POST.get('address_street')}, {request.POST.get('address_city')}"

            # 2. 创建主订单 (Main Order)
            order = Order.objects.create(
                user=request.user,
                status="Pending",
                shipping_info=shipping_info,
                status_updated_at=timezone.now()
            )

            # 3. 创建子项 (OrderItems)
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item,
                    quantity=item.quantity,
                    price=item.price
                )
                # 扣减库存
                item.stock -= item.quantity
                item.save()

            # 4. 清空购物车
            if request.user.is_authenticated:
                Cart.objects.filter(user=request.user).delete()
            else:
                request.session['cart'] = {}

            return redirect('order_confirmation', order_id=order.id)

    context = {
        'cart_items': cart_items,
        'total': total_price,
        'saved_addresses': saved_addresses
    }
    return render(request, 'checkout.html', context)

# ✨✨✨ 核心修改：确认页面 (显示所有子项) ✨✨✨
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # 通过反向关联 items 获取商品
    order_items = order.items.select_related('product').all()

    context = {
        'order': order,
        'order_items': order_items,
        'total_amount': order.total_price # 使用 Model 中定义的 @property
    }
    return render(request, 'order_confirmation.html', context)

# ✨✨✨ 核心修改：商家订单处理 (状态机+时间更新) ✨✨✨
@login_required
def order_process(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if getattr(request.user, 'role', '') != 'vendor':
        raise PermissionDenied

    if request.method == 'POST':
        new_status = request.POST.get('status')
        current_status = order.status
        allowed = False

        # 状态机逻辑更新：严格控制流转
        if current_status == 'Pending':
            # Pending 只能去 Shipped 或 Cancelled
            if new_status in ['Shipped', 'Cancelled']:
                allowed = True
        elif current_status == 'Shipped':
            # Shipped 只能去 Processed (完成)
            if new_status == 'Processed':
                allowed = True
        # Cancelled 和 Processed 是终态，不允许任何修改

        if allowed:
            order.status = new_status
            order.status_updated_at = timezone.now() # 更新通用时间

            # ✨✨✨ 核心修改：根据 B4 Requirement 记录各阶段时间 ✨✨✨
            if new_status == 'Shipped':
                order.shipped_at = timezone.now()
            elif new_status == 'Processed':
                order.processed_at = timezone.now()
            elif new_status == 'Cancelled':
                order.cancelled_at = timezone.now()

            order.save()
            messages.success(request, f"Order #{order.id} status updated to {new_status}.")
        else:
            # 增加更具体的错误提示，帮助调试
            if current_status == 'Pending' and new_status == 'Processed':
                msg = "Invalid Action: Pending orders must be Shipped first."
            elif current_status == 'Shipped' and new_status == 'Pending':
                msg = "Invalid Action: Cannot revert Shipped order to Pending."
            elif current_status in ['Cancelled', 'Processed']:
                msg = f"Invalid Action: Order is already {current_status} and cannot be changed."
            else:
                msg = f"Invalid Action: Cannot change status from {current_status} to {new_status}."
            messages.error(request, msg)

        return redirect('order_process', order_id=order.id)

    return render(request, 'order_process.html', {'order': order})

# ✨✨✨ 核心修改：取消订单 (时间更新) ✨✨✨
@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status == 'Pending':
        order.status = 'Cancelled'
        order.status_updated_at = timezone.now() # 更新通用时间
        order.cancelled_at = timezone.now() # ✨ 核心修改：记录取消时间
        order.save()
        messages.success(request, f"Order #{order.id} has been cancelled successfully.")
    else:
        messages.error(request, "This order cannot be cancelled at this stage.")

    return redirect(f"{reverse('user_profile')}?tab=orders")

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

    # ✨✨✨ 核心逻辑：从 Session 提取可能因为敏感词被拦截的草稿和报错 ✨✨✨
    # 这样页面刷新后文字依然保留在文本框里
    for r in page_obj:
        draft = request.session.pop(f'draft_reply_{r.id}', None)
        error = request.session.pop(f'reply_error_{r.id}', None)
        if draft is not None:
            r.draft_reply = draft
        if error is not None:
            r.reply_error = error

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
            # ✨✨✨ 商家端敏感词拦截核心逻辑 ✨✨✨
            # 调用 utils.py 中的 DFA 过滤器检测
            is_sensitive, filtered_text = sensitive_filter.filter(reply_text)

            if is_sensitive:
                # 命中敏感词：将原文字和统一的报错信息存入 session，防止清空
                request.session[f'draft_reply_{review.id}'] = reply_text
                request.session[f'reply_error_{review.id}'] = "Warning: Your response contains inappropriate language (such as profanity or sensitive topics). Please edit your reply before posting."
            else:
                # 未命中：允许保存
                review.vendor_reply = reply_text
                review.replied_at = timezone.now()
                review.save()
                messages.success(request, 'Reply posted successfully.')

    # 返回上一页 (确保如果您在第3页回复，报错刷新后依然停留在第3页)
    return redirect(request.META.get('HTTP_REFERER', 'vendor_reviews'))