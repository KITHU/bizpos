from rest_framework import serializers
from .models import Stock


class StockSerializer(serializers.ModelSerializer):
    """Serializer for Stock entries"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    is_expired = serializers.SerializerMethodField(read_only=True)
    days_to_expiry = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Stock
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'batch_no', 'expiry_date', 'quantity', 'unit_cost',
            'location', 'is_active', 'is_expired', 'days_to_expiry',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'product_name', 'product_sku',
            'is_expired', 'days_to_expiry', 'created_at', 'updated_at'
        ]

    def get_is_expired(self, obj):
        """Return True if this stock batch is expired"""
        return obj.is_expired

    def get_days_to_expiry(self, obj):
        """Return number of days until expiry (None if unknown)"""
        return obj.days_to_expiry