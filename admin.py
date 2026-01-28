from django.contrib import admin

# Register your models here.

from .models import Category, Tag, Product, ProductImage, Order

# 注册模型到 admin
admin.site.register(Category)
admin.site.register(Tag)
admin.site.register(Product)
admin.site.register(ProductImage)
admin.site.register(Order)  # 注册 Order 模型
