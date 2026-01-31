"""
Pytest configuration and fixtures for BizPos tests
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.products.models import Category, Product, Stock, StockMovement


@pytest.fixture
def api_client():
    """Return an API client for testing"""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def category(db):
    """Create a test category"""
    return Category.objects.create(
        name='Electronics',
        description='Electronic products'
    )


@pytest.fixture
def product(db, category):
    """Create a test product"""
    return Product.objects.create(
        name='Test Product',
        category=category,
        unit_cost=Decimal('100.00'),
        least_selling_price=Decimal('120.00'),
        wholesale_price=Decimal('150.00'),
        retail_price=Decimal('180.00'),
        reorder_level=10,
        quantity=0
    )


@pytest.fixture
def product_with_stock(db, product):
    """Create a product with stock"""
    Stock.objects.create(
        product=product,
        batch_no='BATCH001',
        quantity=50,
        unit_cost=Decimal('100.00')
    )
    product.refresh_from_db()
    return product


@pytest.fixture
def stock_entry(db, product):
    """Create a stock entry"""
    return Stock.objects.create(
        product=product,
        batch_no='TEST-BATCH-001',
        quantity=100,
        unit_cost=Decimal('100.00'),
        location='Warehouse A'
    )
