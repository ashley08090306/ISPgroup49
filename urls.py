from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    # 系统自带的 admin，留着给你自己用，商家不用这个
    path('admin/', admin.site.urls),

    # 公共页面
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # === 商家专属页面 (Custom Vendor Portal) ===
    path('vendor/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('vendor/products/', views.vendor_products, name='vendor_products'),
    path('vendor/products/add/', views.vendor_add_product, name='vendor_add_product'),
    path('vendor/orders/', views.vendor_orders, name='vendor_orders'),
    path('vendor/myshop/', views.vendor_myshop, name='vendor_myshop'),
]