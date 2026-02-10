from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Product, Category, Tag, ProductImage, Order, OrderItem, ShippingAddress, ShopProfile, Review, ReviewMedia, Payment, Cart, CartItem

# 1. 自定义用户管理 (保留原样)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('username', 'email', 'role', 'gender', 'birth_date', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('role', 'gender', 'birth_date')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra Info', {'fields': ('role', 'gender', 'birth_date')}),
    )

# 2. 商品图片内联 (保留原样)
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

# 3. 商品管理 (保留原样)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'brand', 'price', 'stock', 'available', 'category')
    list_filter = ('brand', 'category', 'available')
    search_fields = ('product_name', 'brand')
    inlines = [ProductImageInline]

# 4. 评论媒体内联 (保留原样)
class ReviewMediaInline(admin.TabularInline):
    model = ReviewMedia
    extra = 0

# 5. 评论管理 (保留原样)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'vendor_reply_status', 'created_at')
    list_filter = ('rating', 'created_at')
    inlines = [ReviewMediaInline]
    # Add vendor reply fields to admin details
    fields = ('product', 'user', 'rating', 'comment', 'vendor_reply', 'replied_at', 'created_at')
    readonly_fields = ('created_at',)

    def vendor_reply_status(self, obj):
        return "Replied" if obj.vendor_reply else "Pending"
    vendor_reply_status.short_description = 'Vendor Reply'

# ==================== ✨✨✨ 重点修改区域：订单管理 ✨✨✨ ====================

# 6.1 定义子订单项内联 (OrderItem)
# 这样在查看主订单时，可以直接看到里面买了哪些商品
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0  # 不显示多余空行
    readonly_fields = ('total_price',)  # 只读显示单行总价

# 6.2 订单主表管理 (Order)
class OrderAdmin(admin.ModelAdmin):
    # ❌ 移除了 'product', 'quantity' (因为它们现在在子表里)
    # ✅ 新增 'total_price_display' (计算总价) 和 'status_updated_at'
    list_display = ('id', 'user', 'status', 'total_price_display', 'order_date', 'status_updated_at')
    
    list_filter = ('status', 'order_date')
    search_fields = ('id', 'user__username', 'user__email')
    readonly_fields = ('order_date', 'status_updated_at')

    # ✨ 将子订单挂载进去
    inlines = [OrderItemInline]

    # 计算订单总价用于列表显示
    def total_price_display(self, obj):
        return f"${obj.total_price:.2f}"
    total_price_display.short_description = 'Total Order Value'

# ==================== End Order Changes ====================

# 7. 地址管理 (保留原样)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'city', 'street', 'is_default')
    list_filter = ('category', 'is_default')

# 8. 购物车管理 (保留原样)
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    inlines = [CartItemInline]

# 9. 支付管理 (新增，为了完整性)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'payment_method', 'payment_status', 'payment_date')

# 注册所有模型
admin.site.register(User, CustomUserAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Category)
admin.site.register(Tag)
# 注意：OrderItem 不需要单独注册，它作为 Inline 显示在 Order 里
admin.site.register(Order, OrderAdmin)
admin.site.register(ShippingAddress, ShippingAddressAdmin)
admin.site.register(ShopProfile)
admin.site.register(Review, ReviewAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(Payment, PaymentAdmin)