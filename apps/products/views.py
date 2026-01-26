from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Q, Count, Prefetch

from .models import Category, Product, Stock
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
    StockSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    """CRUD operations for Category"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Annotate products_count to avoid N+1 queries"""
        return Category.objects.annotate(
            products_count=Count('products', filter=Q(products__is_active=True))
        ).order_by('name')


class ProductViewSet(viewsets.ModelViewSet):
    """CRUD operations for Product"""
    queryset = Product.objects.all()  # Base queryset for router
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active', 'is_online', 'is_special', 'taxable']
    search_fields = ['name', 'sku', 'barcode', 'description', 'category__name']
    ordering_fields = ['name', 'retail_price', 'quantity', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Optimize queryset with annotated total_stock and prefetch active stock"""
        active_stock_prefetch = Prefetch(
            'stock_entries',
            queryset=Stock.objects.filter(is_active=True)
        )
        
        return Product.objects.select_related('category').prefetch_related(
            active_stock_prefetch
        ).annotate(
            total_stock=Sum('stock_entries__quantity', filter=Q(stock_entries__is_active=True))
        ).order_by('name')

    def get_serializer_class(self):
        """Choose serializer depending on action"""
        if self.action == 'list':
            return ProductListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer


class StockViewSet(viewsets.ModelViewSet):
    """CRUD operations for Stock"""
    queryset = Stock.objects.all()  # Base queryset for router
    serializer_class = StockSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'is_active']
    search_fields = ['product__name', 'product__sku', 'batch_no', 'location']
    ordering_fields = ['expiry_date', 'quantity', 'created_at']
    ordering = ['expiry_date', 'created_at']

    def get_queryset(self):
        """Select related product and category to optimize queries"""
        return Stock.objects.select_related(
            'product', 'product__category'
        ).order_by('expiry_date', 'created_at')