"""django_library URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include, re_path
from library.views import library_home, catalog, users, reviews, add_review


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', library_home, name='library_home'),
    path('catalog/', catalog, name='catalog'),
    path('accounts/', include('allauth.urls')),
    path('users/', users, name='users'),
    path('reviews/', reviews, name='reviews'),
    path('add_review/', add_review, name='add_review'),
    

]
