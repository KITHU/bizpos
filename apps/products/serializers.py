from rest_framework import serializers
from django.db.models import Sum
from .models import Category, Product, Stock
from .stock_serializer import StockSerializer


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    products_count = serializers.IntegerField(read_only=True)  # Use annotated field

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'products_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'products_count']


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed product serializer with stock info"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    stock_entries = StockSerializer(many=True, read_only=True)
    total_stock = serializers.SerializerMethodField(read_only=True)
    profit_margin = serializers.SerializerMethodField(read_only=True)
    is_low_stock = serializers.SerializerMethodField(read_only=True)
    available_stock = serializers.SerializerMethodField(read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'barcode', 'name', 'description',
            'category', 'category_name',
            'unit_cost', 'least_selling_price', 'wholesale_price', 'retail_price',
            'quantity', 'reorder_level', 'unit', 'pack_size',
            'taxable', 'discount_percent', 'is_special', 'is_online', 'is_active',
            'total_stock', 'available_stock', 'profit_margin', 'is_low_stock', 
            'discounted_price', 'stock_entries',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'sku',
            'total_stock', 'available_stock', 'profit_margin',
            'is_low_stock', 'discounted_price', 'category_name', 'stock_entries'
        ]

    def get_total_stock(self, obj):
        return obj.stock_entries.filter(is_active=True).aggregate(
            total=Sum('quantity')
        )['total'] or 0

    def get_profit_margin(self, obj):
        return obj.profit_margin

    def get_is_low_stock(self, obj):
        return obj.is_low_stock

    def get_available_stock(self, obj):
        return obj.available_stock

    def get_discounted_price(self, obj):
        return obj.discounted_price


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing products in inventory overview"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    total_stock = serializers.IntegerField(read_only=True)  # Use annotated field
    is_low_stock = serializers.SerializerMethodField(read_only=True)
    discounted_price = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'barcode', 'name', 'category_name',
            'retail_price', 'discounted_price', 'quantity', 'total_stock', 
            'reorder_level', 'is_low_stock', 'is_active'
        ]
        read_only_fields = ['category_name', 'total_stock', 'is_low_stock', 'discounted_price']

    def get_is_low_stock(self, obj):
        """Return True if product quantity is below reorder level"""
        return obj.is_low_stock

    def get_discounted_price(self, obj):
        """Return retail price after discount (if any)"""
        return obj.discounted_price


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating or updating Product entries"""
    
    class Meta:
        model = Product
        # Only include fields users can provide
        fields = [
            'barcode', 'name', 'description', 'category',
            'unit_cost', 'least_selling_price', 'wholesale_price', 'retail_price',
            'quantity', 'reorder_level', 'unit', 'pack_size',
            'taxable', 'discount_percent', 'is_special', 'is_online', 'is_active'
        ]
        # All fields are writable; SKU is generated automatically
        extra_kwargs = {
            'barcode': {'required': False, 'allow_blank': True, 'allow_null': True},
            'description': {'required': False, 'allow_blank': True, 'allow_null': True},
        }

    def validate(self, attrs):
        """
        Ensure pricing hierarchy is correct:
        retail >= wholesale >= least_selling >= unit_cost
        """
        unit_cost = attrs.get('unit_cost', getattr(self.instance, 'unit_cost', None))
        least_selling = attrs.get('least_selling_price', getattr(self.instance, 'least_selling_price', None))
        wholesale = attrs.get('wholesale_price', getattr(self.instance, 'wholesale_price', None))
        retail = attrs.get('retail_price', getattr(self.instance, 'retail_price', None))

        if retail is not None and wholesale is not None and retail < wholesale:
            raise serializers.ValidationError("Retail price cannot be less than wholesale price.")
        
        if wholesale is not None and least_selling is not None and wholesale < least_selling:
            raise serializers.ValidationError("Wholesale price cannot be less than least selling price.")
        
        if least_selling is not None and unit_cost is not None and least_selling < unit_cost:
            raise serializers.ValidationError("Least selling price cannot be less than unit cost.")

        return attrs


class SKUPreviewSerializer(serializers.Serializer):
    """Serializer for SKU preview requests"""
    category_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    product_name = serializers.CharField(max_length=255, required=False, allow_blank=True)