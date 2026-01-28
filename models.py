from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings  # 导入 settings 用于引用用户模型

# ==================== 1. 用户与认证系统 ====================

class User(AbstractUser):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')

    # 确保邮箱是唯一的
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username


class ShippingAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')

    country = models.CharField(max_length=50)
    city = models.CharField(max_length=50)
    district = models.CharField(max_length=50)
    street = models.CharField(max_length=100)
    detail_address = models.CharField(max_length=255)

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

    # ✨✨✨ 新增：视频字段 (B功能 Requirement) ✨✨✨
    # 视频会保存在 media/product_videos/ 文件夹下
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


# ==================== 5. 订单系统 ====================

class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE) # 买家
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20)

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

# ✨✨✨ 新增：店铺公共信息表 (Single Shop Profile) ✨✨✨
class ShopProfile(models.Model):
    shop_name = models.CharField(max_length=100, default="My Awesome Shop")
    email = models.EmailField(max_length=100, default="contact@myshop.com")

    # 地址信息
    country = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=50, blank=True)
    district = models.CharField(max_length=50, blank=True)
    street = models.CharField(max_length=100, blank=True)
    detail_address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.shop_name



