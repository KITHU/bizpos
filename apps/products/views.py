from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Q, Count, Prefetch, F, Case, When, DecimalField
from django.shortcuts import get_object_or_404

from .models import Category, Product, Stock, StockMovement
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer,
)
from .stock_serializer import StockSerializer
from .movement_serializer import (
    StockMovementSerializer,
    StockOperationSerializer,
    StockAddSerializer,
    StockRemoveSerializer,
    StockAdjustSerializer,
    MovementSummarySerializer,
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
        elif self.action in ['add_stock', 'remove_stock', 'adjust_stock']:
            return StockOperationSerializer
        return ProductDetailSerializer

    @action(detail=True, methods=['post'])
    def add_stock(self, request, pk=None):
        """Add stock to a product"""
        product = self.get_object()
        serializer = StockAddSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                stock = product.add_stock(
                    quantity=serializer.validated_data['quantity'],
                    unit_cost=serializer.validated_data['unit_cost'],
                    batch_no=serializer.validated_data.get('batch_no'),
                    expiry_date=serializer.validated_data.get('expiry_date'),
                    location=serializer.validated_data.get('location'),
                    reference=serializer.validated_data.get('reference', ''),
                    note=serializer.validated_data.get('note', '')
                )
                
                return Response({
                    'message': f'Added {serializer.validated_data["quantity"]} units to {product.name}',
                    'stock_id': stock.id,
                    'batch_no': stock.batch_no,
                    'new_total_quantity': product.quantity
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def remove_stock(self, request, pk=None):
        """Remove stock from a product"""
        product = self.get_object()
        serializer = StockRemoveSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                movements = product.remove_stock(
                    quantity=serializer.validated_data['quantity'],
                    reference=serializer.validated_data.get('reference', ''),
                    note=serializer.validated_data.get('note', ''),
                    use_fifo=serializer.validated_data.get('use_fifo', True)
                )
                
                return Response({
                    'message': f'Removed {serializer.validated_data["quantity"]} units from {product.name}',
                    'movements_created': len(movements),
                    'new_total_quantity': product.quantity
                }, status=status.HTTP_200_OK)
                
            except ValueError as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        """Adjust product stock to a specific quantity"""
        product = self.get_object()
        serializer = StockAdjustSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                movement = product.adjust_stock(
                    new_total_quantity=serializer.validated_data['new_total_quantity'],
                    reference=serializer.validated_data.get('reference', ''),
                    note=serializer.validated_data.get('note', '')
                )
                
                return Response({
                    'message': f'Adjusted {product.name} stock to {serializer.validated_data["new_total_quantity"]} units',
                    'movement_id': movement.id if movement else None,
                    'new_total_quantity': product.quantity
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        """Get stock movements for a product"""
        product = self.get_object()
        movements = product.movements.all()
        
        # Apply pagination
        page = self.paginate_queryset(movements)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)


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

    def create(self, request, *args, **kwargs):
        """
        Override create to use product.add_stock() method for proper movement tracking.
        This ensures StockMovement records are created automatically.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Extract data
        product_id = serializer.validated_data['product'].id
        quantity = serializer.validated_data['quantity']
        unit_cost = serializer.validated_data['unit_cost']
        batch_no = serializer.validated_data.get('batch_no')
        expiry_date = serializer.validated_data.get('expiry_date')
        location = serializer.validated_data.get('location', '')
        
        # Get the product
        product = get_object_or_404(Product, id=product_id)
        
        # Use product.add_stock() to ensure movement tracking
        try:
            stock = product.add_stock(
                quantity=quantity,
                unit_cost=unit_cost,
                batch_no=batch_no,
                expiry_date=expiry_date,
                location=location,
                reference=request.data.get('reference', ''),
                note=request.data.get('note', 'Stock added via API')
            )
            
            # Return the created stock
            output_serializer = self.get_serializer(stock)
            headers = self.get_success_headers(output_serializer.data)
            return Response(
                output_serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        """
        Override update to create movement records for quantity changes.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        old_quantity = instance.quantity
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        new_quantity = serializer.validated_data.get('quantity', old_quantity)
        quantity_diff = new_quantity - old_quantity
        
        # If quantity changed, create a movement record
        if quantity_diff != 0:
            from django.apps import apps
            StockMovement = apps.get_model('products', 'StockMovement')
            
            movement_type = 'IN' if quantity_diff > 0 else 'OUT'
            
            StockMovement.objects.create(
                product=instance.product,
                stock=instance,
                movement_type='ADJUST',  # Use ADJUST for manual stock updates
                quantity=quantity_diff,
                unit_cost=instance.unit_cost,
                reference=request.data.get('reference', ''),
                note=request.data.get('note', f'Stock updated via API: {old_quantity} → {new_quantity}')
            )
        
        self.perform_update(serializer)
        
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        
        return Response(serializer.data)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only operations for StockMovement (movements are created via product operations)"""
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'movement_type', 'stock']
    search_fields = ['product__name', 'product__sku', 'reference', 'note']
    ordering_fields = ['created_at', 'quantity']
    ordering = ['-created_at']

    def get_queryset(self):
        """Select related product and stock to optimize queries"""
        return StockMovement.objects.select_related(
            'product', 'product__category', 'stock'
        ).order_by('-created_at')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get movement summary statistics"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calculate summary statistics
        summary = queryset.aggregate(
            total_movements=Count('id'),
            stock_in_total=Sum(
                Case(When(movement_type='IN', then='quantity'), default=0)
            ),
            stock_out_total=Sum(
                Case(When(movement_type='OUT', then='quantity'), default=0)
            ),
            adjustments_total=Sum(
                Case(When(movement_type='ADJUST', then='quantity'), default=0)
            ),
            total_value_in=Sum(
                Case(
                    When(movement_type='IN', then=F('quantity') * F('unit_cost')),
                    default=0,
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            ),
            total_value_out=Sum(
                Case(
                    When(movement_type='OUT', then=F('quantity') * F('unit_cost')),
                    default=0,
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
        )
        
        # Calculate net values
        summary['net_quantity'] = (summary['stock_in_total'] or 0) + (summary['stock_out_total'] or 0) + (summary['adjustments_total'] or 0)
        summary['net_value'] = (summary['total_value_in'] or 0) + (summary['total_value_out'] or 0)
        
        # Convert None values to 0
        for key, value in summary.items():
            if value is None:
                summary[key] = 0
        
        serializer = MovementSummarySerializer(summary)
        return Response(serializer.data)