from django.contrib import admin
from .models import Category, Product, Stock, ProductSKUSequence


@admin.register(ProductSKUSequence)
class ProductSKUSequenceAdmin(admin.ModelAdmin):
    list_display = ['prefix', 'last_number']
    search_fields = ['prefix']
    readonly_fields = ['prefix']  # Don't allow editing prefix manually
    
    def has_add_permission(self, request):
        # Prevent manual creation - these should be auto-created
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


class StockInline(admin.TabularInline):
    model = Stock
    extra = 1
    fields = ['batch_no', 'expiry_date', 'quantity', 'unit_cost', 'location', 'is_active']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'sku', 'name', 'category', 'retail_price', 'discounted_price',
        'quantity', 'is_low_stock', 'is_active', 'created_at'
    ]
    list_filter = ['category', 'is_active', 'is_online', 'is_special', 'taxable']
    search_fields = ['name', 'sku', 'barcode', 'category__name']
    readonly_fields = ['created_at', 'updated_at', 'sku', 'profit_margin', 'available_stock', 'discounted_price']
    inlines = [StockInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sku', 'barcode', 'name', 'description', 'category')
        }),
        ('Pricing', {
            'fields': ('unit_cost', 'least_selling_price', 'wholesale_price', 'retail_price', 'discount_percent', 'discounted_price')
        }),
        ('Inventory', {
            'fields': ('quantity', 'available_stock', 'reorder_level', 'unit', 'pack_size')
        }),
        ('Analytics', {
            'fields': ('profit_margin',),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('taxable', 'is_special', 'is_online', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Low Stock'

    def discounted_price(self, obj):
        return f"${obj.discounted_price}"
    discounted_price.short_description = 'Discounted Price'

    def profit_margin(self, obj):
        return f"{obj.profit_margin:.1f}%"
    profit_margin.short_description = 'Profit Margin'

    def available_stock(self, obj):
        return f"{obj.available_stock} units"
    available_stock.short_description = 'Available Stock'


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'batch_no', 'quantity', 'unit_cost', 
        'expiry_date', 'is_expired', 'days_to_expiry', 'location', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'expiry_date', 'created_at', 'product__category']
    search_fields = ['product__name', 'product__sku', 'batch_no', 'location']
    readonly_fields = ['created_at', 'updated_at', 'is_expired', 'days_to_expiry']
    
    fieldsets = (
        ('Product Information', {
            'fields': ('product', 'batch_no')
        }),
        ('Inventory Details', {
            'fields': ('quantity', 'unit_cost', 'expiry_date', 'location')
        }),
        ('Status', {
            'fields': ('is_active', 'is_expired', 'days_to_expiry')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = 'Expired'

    def days_to_expiry(self, obj):
        days = obj.days_to_expiry
        if days is None:
            return "No expiry"
        elif days < 0:
            return f"Expired {abs(days)} days ago"
        elif days == 0:
            return "Expires today"
        else:
            return f"{days} days"
    days_to_expiry.short_description = 'Days to Expiry'