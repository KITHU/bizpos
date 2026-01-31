"""
Unit tests for BizPos models
"""
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.products.models import Category, Product, Stock, StockMovement, generate_sku


@pytest.mark.django_db
class TestCategory:
    """Test Category model"""
    
    def test_create_category(self):
        """Test creating a category"""
        category = Category.objects.create(
            name='Test Category',
            description='Test description'
        )
        assert category.name == 'Test Category'
        assert category.description == 'Test description'
        assert str(category) == 'Test Category'
    
    def test_category_unique_name(self):
        """Test that category names must be unique"""
        Category.objects.create(name='Electronics')
        with pytest.raises(Exception):  # IntegrityError
            Category.objects.create(name='Electronics')


@pytest.mark.django_db
class TestProduct:
    """Test Product model"""
    
    def test_create_product(self, category):
        """Test creating a product"""
        product = Product.objects.create(
            name='Test Product',
            category=category,
            unit_cost=Decimal('100.00'),
            least_selling_price=Decimal('120.00'),
            wholesale_price=Decimal('150.00'),
            retail_price=Decimal('180.00')
        )
        assert product.name == 'Test Product'
        assert product.category == category
        assert product.sku  # SKU should be auto-generated
        assert len(product.sku) == 12  # XXX-XXX-0001 format
    
    def test_sku_auto_generation(self, category):
        """Test that SKU is auto-generated"""
        product = Product.objects.create(
            name='Smartphone X1',
            category=category,
            unit_cost=Decimal('200.00'),
            least_selling_price=Decimal('250.00'),
            wholesale_price=Decimal('300.00'),
            retail_price=Decimal('350.00')
        )
        assert product.sku
        assert product.sku.startswith('ELE-SMA')  # Electronics-Smartphone
    
    def test_profit_margin_calculation(self, product):
        """Test profit margin property"""
        # unit_cost=100, retail_price=180
        # margin = ((180-100)/100) * 100 = 80%
        assert product.profit_margin == 80.0
    
    def test_is_low_stock(self, product):
        """Test low stock detection"""
        product.quantity = 5
        product.reorder_level = 10
        assert product.is_low_stock is True
        
        product.quantity = 15
        assert product.is_low_stock is False
    
    def test_discounted_price(self, product):
        """Test discounted price calculation"""
        product.retail_price = Decimal('100.00')
        product.discount_percent = Decimal('10.00')
        assert product.discounted_price == 90.0
    
    def test_available_stock_with_pack_size(self, product):
        """Test available stock calculation with pack size"""
        product.quantity = 10
        product.pack_size = 5
        assert product.available_stock == 50


@pytest.mark.django_db
class TestStock:
    """Test Stock model"""
    
    def test_create_stock(self, product):
        """Test creating a stock entry"""
        stock = Stock.objects.create(
            product=product,
            batch_no='BATCH001',
            quantity=100,
            unit_cost=Decimal('95.00'),
            location='Warehouse A'
        )
        assert stock.product == product
        assert stock.batch_no == 'BATCH001'
        assert stock.quantity == 100
    
    def test_stock_updates_product_quantity(self, product):
        """Test that creating stock updates product quantity"""
        assert product.quantity == 0
        
        Stock.objects.create(
            product=product,
            batch_no='BATCH001',
            quantity=50,
            unit_cost=Decimal('100.00')
        )
        
        product.refresh_from_db()
        assert product.quantity == 50
    
    def test_is_expired_property(self, stock_entry):
        """Test is_expired property"""
        from datetime import date, timedelta
        
        # Not expired
        stock_entry.expiry_date = date.today() + timedelta(days=30)
        assert stock_entry.is_expired is False
        
        # Expired
        stock_entry.expiry_date = date.today() - timedelta(days=1)
        assert stock_entry.is_expired is True
    
    def test_days_to_expiry(self, stock_entry):
        """Test days_to_expiry property"""
        from datetime import date, timedelta
        
        stock_entry.expiry_date = date.today() + timedelta(days=30)
        assert stock_entry.days_to_expiry == 30


@pytest.mark.django_db
class TestStockMovement:
    """Test StockMovement model"""
    
    def test_create_movement(self, product, stock_entry):
        """Test creating a stock movement"""
        movement = StockMovement.objects.create(
            product=product,
            stock=stock_entry,
            movement_type=StockMovement.IN,
            quantity=50,
            unit_cost=Decimal('100.00'),
            reference='PO-001'
        )
        assert movement.product == product
        assert movement.movement_type == 'IN'
        assert movement.quantity == 50
    
    def test_movement_updates_stock_quantity(self, product, stock_entry):
        """Test that movement updates stock quantity"""
        initial_qty = stock_entry.quantity
        
        StockMovement.objects.create(
            product=product,
            stock=stock_entry,
            movement_type=StockMovement.IN,
            quantity=25,
            unit_cost=Decimal('100.00')
        )
        
        stock_entry.refresh_from_db()
        assert stock_entry.quantity == initial_qty + 25
    
    def test_total_value_property(self, product, stock_entry):
        """Test total_value property"""
        movement = StockMovement.objects.create(
            product=product,
            stock=stock_entry,
            movement_type=StockMovement.IN,
            quantity=10,
            unit_cost=Decimal('50.00')
        )
        assert movement.total_value == Decimal('500.00')


@pytest.mark.django_db
class TestProductStockOperations:
    """Test product stock operation methods"""
    
    def test_add_stock(self, product):
        """Test adding stock to a product"""
        stock = product.add_stock(
            quantity=50,
            unit_cost=Decimal('100.00'),
            batch_no='BATCH001',
            reference='PO-001'
        )
        
        assert stock.quantity == 50
        assert stock.batch_no == 'BATCH001'
        product.refresh_from_db()
        assert product.quantity == 50
        
        # Check movement was created
        movements = product.movements.all()
        assert movements.count() == 1
        assert movements.first().movement_type == 'IN'
    
    def test_remove_stock_fifo(self, product):
        """Test removing stock using FIFO"""
        # Add two batches
        product.add_stock(50, Decimal('100.00'), 'BATCH001')
        product.add_stock(30, Decimal('95.00'), 'BATCH002')
        
        product.refresh_from_db()
        assert product.quantity == 80
        
        # Remove 60 units (should take 50 from BATCH001 and 10 from BATCH002)
        movements = product.remove_stock(60, reference='SALE-001')
        
        product.refresh_from_db()
        assert product.quantity == 20
        assert len(movements) == 2  # Two movements created
    
    def test_remove_stock_insufficient(self, product):
        """Test removing more stock than available"""
        product.add_stock(30, Decimal('100.00'), 'BATCH001')
        
        with pytest.raises(ValueError, match='Insufficient stock'):
            product.remove_stock(50)
    
    def test_adjust_stock(self, product):
        """Test adjusting stock to specific quantity"""
        product.add_stock(50, Decimal('100.00'), 'BATCH001')
        product.refresh_from_db()
        assert product.quantity == 50
        
        # Adjust to 75
        movement = product.adjust_stock(75, reference='ADJ-001')
        
        product.refresh_from_db()
        assert product.quantity == 75
        assert movement.movement_type == 'ADJUST'


@pytest.mark.django_db
class TestSKUGeneration:
    """Test SKU generation logic"""
    
    def test_sku_format(self):
        """Test SKU format is correct"""
        sku = generate_sku('Electronics', 'Smartphone')
        assert len(sku) == 12
        assert sku.count('-') == 2
        parts = sku.split('-')
        assert len(parts) == 3
        assert len(parts[0]) == 3  # Category prefix
        assert len(parts[1]) == 3  # Product prefix
        assert len(parts[2]) == 4  # Sequence number
    
    def test_sku_sequence_increment(self):
        """Test that SKU sequence increments"""
        sku1 = generate_sku('Test', 'Product')
        sku2 = generate_sku('Test', 'Product')
        
        # Extract sequence numbers
        seq1 = int(sku1.split('-')[2])
        seq2 = int(sku2.split('-')[2])
        
        assert seq2 == seq1 + 1
