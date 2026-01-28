from django.contrib import admin
from django.urls import path
from django.conf import settings  # 导入设置，为了处理图片
from django.conf.urls.static import static # 导入静态文件处理函数
from core import views  # 导入 core 应用的视图

urlpatterns = [
    # === 1. 系统管理 ===
    path('admin/', admin.site.urls), # 保留着，万一数据库出问题你们还得进去修

    # === 2. 公共页面 (Public) ===
    path('', views.home, name='home'),

    # === 3. 认证系统 (Authentication) ===
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # === 4. 商家门户 (Vendor Portal) ===
    # 仪表盘
    path('vendor/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),

    # 店铺信息设置
    path('vendor/myshop/', views.vendor_myshop, name='vendor_myshop'),

    # 订单管理
    path('vendor/orders/', views.vendor_orders, name='vendor_orders'),

    # === 5. 商品管理 (Product Management) ===
    # 商品列表
    path('vendor/products/', views.vendor_products, name='vendor_products'),

    # 添加商品
    path('vendor/products/add/', views.vendor_add_product, name='vendor_add_product'),

    path('vendor/products/edit/<int:product_id>/', views.vendor_edit_product, name='vendor_edit_product'),

    # ✨✨✨ 新增：删除单张图片 ✨✨✨
    path('vendor/products/image/delete/<int:image_id>/', views.delete_product_image, name='delete_product_image'),

    # 商品上架/下架 (Toggle Availability)
    # 注意：这里用了 <int:product_id> 来接收特定商品的 ID
    path('vendor/products/toggle/<int:product_id>/', views.toggle_product_availability, name='toggle_product_availability'),

    path('vendor/products/delete/<int:product_id>/', views.vendor_delete_product, name='vendor_delete_product'),
]

# === 6. 图片/媒体文件配置 (Block B 多图功能必需) ===
# 这段代码的意思是：在 Debug 模式下，告诉 Django 去 MEDIA_ROOT 找上传的图片
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)