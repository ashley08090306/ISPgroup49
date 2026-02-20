
"""
Django settings for myshop project.
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static, serve
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register, name="register"),
    path("product/<int:product_id>/", views.product_detail, name="product_detail"),

    # User Profile URLs
    path("profile/", views.user_profile, name="user_profile"),
    path("profile/update-info/", views.update_profile_info, name="update_profile_info"),
    path("profile/change-password/", views.change_password, name="change_password"),
    path("profile/add-address/", views.add_address, name="add_address"),
    path("profile/delete-address/<int:address_id>/", views.delete_address, name="delete_address"),
    path("profile/update-address/<int:address_id>/", views.update_address, name="update_address"),
    path("profile/delete-review/<int:review_id>/", views.delete_review, name="delete_review"),

    # Cart URLs
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("cart/", views.cart_view, name="cart_view"),
    path("cart/update/", views.update_cart, name="update_cart"),

    # Vendor URLs
    path("vendor/dashboard/", views.vendor_dashboard, name="vendor_dashboard"),
    path("vendor/myshop/", views.vendor_myshop, name="vendor_myshop"),
    path("vendor/products/", views.vendor_products, name="vendor_products"),
    path("vendor/products/add/", views.vendor_add_product, name="vendor_add_product"),
    path("vendor/products/edit/<int:product_id>/", views.vendor_edit_product, name="vendor_edit_product"),
    path("vendor/products/delete/<int:product_id>/", views.vendor_delete_product, name="vendor_delete_product"),
    path("vendor/products/toggle/<int:product_id>/", views.toggle_product_availability, name="toggle_product_availability"),
    path("vendor/products/image/delete/<int:image_id>/", views.delete_product_image, name="delete_product_image"),
    path("vendor/orders/", views.vendor_orders, name="vendor_orders"),

    # ✨ NEW: Vendor Review URLs ✨
    path("vendor/reviews/", views.vendor_reviews, name="vendor_reviews"),
    path("vendor/reviews/reply/<int:review_id>/", views.vendor_reply_review, name="vendor_reply_review"),

    path('heartbeat/', views.heartbeat, name='heartbeat'),
    path('vendor/product/<int:product_id>/delete-video/', views.delete_product_video, name='delete_product_video'),

    path("checkout/", views.checkout, name="checkout"),
    path("order/confirmation/<int:order_id>/", views.order_confirmation, name="order_confirmation"),
    path('order/process/<int:order_id>/', views.order_process, name='order_process'),
    path('product/<int:product_id>/reviews/', views.all_reviews, name='all_reviews'),
    path('order/cancel/<int:order_id>/', views.cancel_order, name='cancel_order'),

    path('api/reviews/<int:review_id>/like/', views.toggle_review_like, name='toggle_review_like'),
    path("profile/append-review/<int:review_id>/", views.append_review, name="append_review"),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]
