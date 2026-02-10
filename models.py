from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone # ✨ 引入 timezone 用于处理时间

# ==================== 1. 用户与认证系统 ====================

class User(AbstractUser):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
    )

    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Prefer not to say'),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')

    # 个人资料字段
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=2, choices=GENDER_CHOICES, default='N')

    # 确保邮箱是唯一的
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username


class ShippingAddress(models.Model):
    CATEGORY_CHOICES = (
        ('home', 'Home'),
        ('office', 'Office'),
        ('school', 'School'),
        ('other', 'Other'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')

    country = models.CharField(max_length=50)
    city = models.CharField(max_length=50)
    district = models.CharField(max_length=50)
    street = models.CharField(max_length=100)
    detail_address = models.CharField(max_length=255)
    is_default = models.BooleanField(default=False)

    # 地址分类
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')

    def __str__(self):
        return f"{self.street}, {self.city}"


# ==================== 2. 商品属性 (分类与标签) ====================

class Category(models.Model):
    category_name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.category_name

class Tag(models.Model):
    tag_name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.tag_name


# ==================== 3. 商品核心模型 ====================

class Product(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE) # 商家
    product_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    brand = models.CharField(max_length=100, null=True, blank=True)
    materials = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    available = models.BooleanField(default=True)
    stock = models.IntegerField(default=1)

    # 关联关系
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    tags = models.ManyToManyField(Tag, related_name='products')

    video = models.FileField(upload_to='product_videos/', null=True, blank=True)

    def __str__(self):
        return self.product_name


# ==================== 4. 商品附属模型 (图片) ====================

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Image for {self.product.product_name}"


# ==================== 5. 订单系统 (核心修改区域) ====================

class Order(models.Model):
    # 状态选项
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Shipped', 'Shipped'),
        ('Processed', 'Processed'), # Changed Delivered -> Processed to match logic
        ('Cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # 买家
    
    # ✨ 改动 1: 移除 product 和 quantity (移到 OrderItem)
    # ✨ 改动 2: 添加状态变更时间 (老师要求)
    status_updated_at = models.DateTimeField(null=True, blank=True)

    # ✨✨✨ 新增：Requirement B4 专用时间字段 ✨✨✨
    shipped_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    order_date = models.DateTimeField(auto_now_add=True)  # 订单日期
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')  # 订单状态

    # ✨ 改动 3: 地址快照 (防止用户改地址表后，历史订单地址变动)
    shipping_info = models.TextField(blank=True, null=True)

    payment_status = models.CharField(max_length=20, default='Unpaid')
    vendor_responded = models.BooleanField(default=False)

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

    # ✨ 辅助方法：计算该订单总价
    @property
    def total_price(self):
        # 聚合查询所有子项的总价
        return sum(item.total_price for item in self.items.all())

# ✨✨✨ 新增：订单明细表 (支持一单多品) ✨✨✨
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    # 记录购买时的单价 (防止商品后续改价影响历史订单)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.product_name}"

    @property
    def total_price(self):
        return self.price * self.quantity


class ShopProfile(models.Model):
    shop_name = models.CharField(max_length=100, default="My Awesome Shop")
    email = models.EmailField(max_length=100, default="contact@myshop.com")
    country = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=50, blank=True)
    district = models.CharField(max_length=50, blank=True)
    street = models.CharField(max_length=100, blank=True)
    detail_address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.shop_name


# ==================== 6. 评论系统 (Review System) ====================

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # ✨ 商家回复字段
    vendor_reply = models.TextField(blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Review {self.id} by {self.user.username}"

    class Meta:
        ordering = ['-created_at']

class ReviewMedia(models.Model):
    MEDIA_TYPES = (
        ('image', 'Image'),
        ('video', 'Video'),
    )
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='media')
    file = models.FileField(upload_to='review_media/')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='image')

    def __str__(self):
        return f"Media for Review {self.review.id}"

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('wechat', 'WeChat'),
        ('alipay', 'Alipay'),
        ('mpay', 'MPay'),
        ('credit_card', 'Credit Card'),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, default='Pending')
    payment_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment for Order {self.order.id}"

# ==================== 7. 购物车持久化 (Persistent Cart) ====================

class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.username}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.product_name}"