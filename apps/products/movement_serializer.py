from rest_framework import serializers
from typing import Optional
from .models import StockMovement, Product, Stock
from decimal import Decimal


class StockMovementSerializer(serializers.ModelSerializer):
    """Serializer for StockMovement entries"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    stock_batch_no = serializers.CharField(source='stock.batch_no', read_only=True)
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    total_value = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'stock', 'stock_batch_no',
            'movement_type', 'movement_type_display',
            'quantity', 'unit_cost', 'total_value',
            'reference', 'note',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'product_name', 'product_sku', 'stock_batch_no',
            'movement_type_display', 'total_value', 'created_at', 'updated_at'
        ]

    def get_total_value(self, obj: StockMovement) -> Optional[float]:
        """Return total value of this movement"""
        return obj.total_value


class StockOperationSerializer(serializers.Serializer):
    """Serializer for stock operations (add/remove/adjust)"""
    operation = serializers.ChoiceField(
        choices=['add', 'remove', 'adjust'],
        help_text="Type of stock operation"
    )
    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Quantity to add/remove (positive number)"
    )
    unit_cost = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        help_text="Cost per unit (required for 'add' operation)"
    )
    batch_no = serializers.CharField(
        max_length=100,
        required=False,
        help_text="Batch number (optional for 'add' operation)"
    )
    expiry_date = serializers.DateField(
        required=False,
        help_text="Expiry date (optional for 'add' operation)"
    )
    location = serializers.CharField(
        max_length=200,
        required=False,
        help_text="Storage location (optional for 'add' operation)"
    )
    reference = serializers.CharField(
        max_length=100,
        required=False,
        help_text="Reference number (invoice, order, etc.)"
    )
    note = serializers.CharField(
        required=False,
        help_text="Additional notes"
    )
    use_fifo = serializers.BooleanField(
        default=True,
        help_text="Use FIFO for 'remove' operation"
    )
    new_total_quantity = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="New total quantity for 'adjust' operation"
    )

    def validate(self, attrs):
        operation = attrs.get('operation')
        
        if operation == 'add':
            if not attrs.get('unit_cost'):
                raise serializers.ValidationError("unit_cost is required for 'add' operation")
        
        elif operation == 'adjust':
            if 'new_total_quantity' not in attrs:
                raise serializers.ValidationError("new_total_quantity is required for 'adjust' operation")
            # Remove quantity validation for adjust operation
            attrs.pop('quantity', None)
        
        return attrs


class StockAddSerializer(serializers.Serializer):
    """Simplified serializer for adding stock"""
    quantity = serializers.IntegerField(min_value=1)
    unit_cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    batch_no = serializers.CharField(max_length=100, required=False)
    expiry_date = serializers.DateField(required=False)
    location = serializers.CharField(max_length=200, required=False)
    reference = serializers.CharField(max_length=100, required=False)
    note = serializers.CharField(required=False)


class StockRemoveSerializer(serializers.Serializer):
    """Simplified serializer for removing stock"""
    quantity = serializers.IntegerField(min_value=1)
    reference = serializers.CharField(max_length=100, required=False)
    note = serializers.CharField(required=False)
    use_fifo = serializers.BooleanField(default=True)


class StockAdjustSerializer(serializers.Serializer):
    """Simplified serializer for adjusting stock"""
    new_total_quantity = serializers.IntegerField(min_value=0)
    reference = serializers.CharField(max_length=100, required=False)
    note = serializers.CharField(required=False)


class MovementSummarySerializer(serializers.Serializer):
    """Serializer for movement summary statistics"""
    total_movements = serializers.IntegerField()
    stock_in_total = serializers.IntegerField()
    stock_out_total = serializers.IntegerField()
    adjustments_total = serializers.IntegerField()
    total_value_in = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_value_out = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_quantity = serializers.IntegerField()
    net_value = serializers.DecimalField(max_digits=15, decimal_places=2)