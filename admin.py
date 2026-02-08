
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Product, Category, Tag, ProductImage, Order, ShippingAddress, ShopProfile, Review, ReviewMedia, Cart, CartItem

# 1. 自定义用户管理
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('username', 'email', 'role', 'gender', 'birth_date', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('role', 'gender', 'birth_date')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra Info', {'fields': ('role', 'gender', 'birth_date')}),
    )

# 2. 商品图片内联
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

# 3. 商品管理
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'brand', 'price', 'stock', 'available', 'category')
    list_filter = ('brand', 'category', 'available')
    search_fields = ('product_name', 'brand')
    inlines = [ProductImageInline]

# 4. 评论媒体内联
class ReviewMediaInline(admin.TabularInline):
    model = ReviewMedia
    extra = 0

# 5. 评论管理
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'vendor_reply_status', 'created_at')
    list_filter = ('rating', 'created_at')
    inlines = [ReviewMediaInline]
    # ✨ Add vendor reply fields to admin details
    fields = ('product', 'user', 'rating', 'comment', 'vendor_reply', 'replied_at', 'created_at')
    readonly_fields = ('created_at',)

    def vendor_reply_status(self, obj):
        return "Replied" if obj.vendor_reply else "Pending"
    vendor_reply_status.short_description = 'Vendor Reply'

# 6. 订单管理
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'quantity', 'total_price_display', 'status', 'order_date')
    list_filter = ('status', 'order_date')

    def total_price_display(self, obj):
        return obj.product.price * obj.quantity
    total_price_display.short_description = 'Total Price'

# 7. 地址管理
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'city', 'street', 'is_default')
    list_filter = ('category', 'is_default')

# 8. 购物车管理
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    inlines = [CartItemInline]

# 注册所有模型
admin.site.register(User, CustomUserAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Category)
admin.site.register(Tag)
admin.site.register(Order, OrderAdmin)
admin.site.register(ShippingAddress, ShippingAddressAdmin)
admin.site.register(ShopProfile)
admin.site.register(Review, ReviewAdmin)
admin.site.register(Cart, CartAdmin)
