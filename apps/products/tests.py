from django.test import TestCase
from django.core.exceptions import ValidationError
from .models import Category, Product, Stock


class ProductSKUTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Electronics",
            description="Electronic products"
        )

    def test_auto_sku_generation(self):
        """Test that SKU is auto-generated when not provided"""
        product = Product.objects.create(
            name="Test Smartphone",
            category=self.category,
            unit_cost=500.00,
            least_selling_price=699.99,
            wholesale_price=799.99,
            retail_price=999.99
        )
        
        # SKU should be auto-generated
        self.assertIsNotNone(product.sku)
        self.assertTrue(len(product.sku) > 0)
        print(f"Auto-generated SKU: {product.sku}")

    def test_manual_sku(self):
        """Test that manual SKU is preserved"""
        manual_sku = "MANUAL-SKU-001"
        product = Product.objects.create(
            sku=manual_sku,
            name="Test Product",
            category=self.category,
            unit_cost=50.00,
            least_selling_price=70.00,
            wholesale_price=80.00,
            retail_price=100.00
        )
        
        self.assertEqual(product.sku, manual_sku)

    def test_sku_uniqueness(self):
        """Test that SKUs are unique"""
        product1 = Product.objects.create(
            name="Product 1",
            category=self.category,
            unit_cost=50.00,
            least_selling_price=70.00,
            wholesale_price=80.00,
            retail_price=100.00
        )
        
        product2 = Product.objects.create(
            name="Product 2",
            category=self.category,
            unit_cost=100.00,
            least_selling_price=140.00,
            wholesale_price=160.00,
            retail_price=200.00
        )
        
        self.assertNotEqual(product1.sku, product2.sku)

    def test_sku_preview_generation(self):
        """Test SKU preview generation"""
        sku = Product.generate_preview_sku(
            category_name="Electronics",
            product_name="Test Product"
        )
        self.assertIsNotNone(sku)
        self.assertTrue(len(sku) > 0)
        # Should follow format: ELE-TES-0001
        self.assertRegex(sku, r'^[A-Z]{3}-[A-Z]{3}-\d{4}$')
        print(f"Preview SKU: {sku}")

    def test_sku_sequence_increment(self):
        """Test that SKU sequence increments properly"""
        from apps.products.models import generate_sku
        
        # Generate first SKU
        sku1 = generate_sku("Electronics", "Smartphone")
        # Generate second SKU with same category/product
        sku2 = generate_sku("Electronics", "Smartphone")
        
        # They should be sequential
        self.assertNotEqual(sku1, sku2)
        # Extract numbers and verify increment
        num1 = int(sku1.split('-')[-1])
        num2 = int(sku2.split('-')[-1])
        self.assertEqual(num2, num1 + 1)
        
        print(f"First SKU: {sku1}")
        print(f"Second SKU: {sku2}")

    def test_sku_prefix_generation(self):
        """Test SKU prefix generation logic"""
        examples = [
            ("Electronics", "Smartphone", "ELE-SMA"),
            ("Food Beverage", "Coca Cola", "FOO-COC"),
            ("Home Garden", "Plant", "HOM-PLA"),
            ("Books", "Python Programming", "BOO-PYT"),
            ("A", "B", "AXX-BXX"),  # Test padding
        ]
        
        for category, product, expected_prefix in examples:
            sku = Product.generate_preview_sku(category, product)
            actual_prefix = '-'.join(sku.split('-')[:2])
            self.assertEqual(actual_prefix, expected_prefix)
            print(f"{category} + {product} = {sku} (prefix: {actual_prefix})")

    def test_price_validation(self):
        """Test price validation constraints"""
        with self.assertRaises(ValidationError):
            product = Product(
                name="Invalid Product",
                category=self.category,
                unit_cost=100.00,
                least_selling_price=50.00,  # Less than unit cost
                wholesale_price=80.00,
                retail_price=90.00
            )
            product.full_clean()

    def test_profit_margin_calculation(self):
        """Test profit margin calculation"""
        product = Product.objects.create(
            name="Test Product",
            category=self.category,
            unit_cost=50.00,
            least_selling_price=70.00,
            wholesale_price=80.00,
            retail_price=100.00
        )
        
        # Profit margin should be 100% ((100-50)/50 * 100)
        self.assertEqual(product.profit_margin, 100.0)

    def test_low_stock_property(self):
        """Test low stock detection"""
        product = Product.objects.create(
            name="Test Product",
            category=self.category,
            unit_cost=50.00,
            least_selling_price=70.00,
            wholesale_price=80.00,
            retail_price=100.00,
            quantity=5,
            reorder_level=10
        )
        
        self.assertTrue(product.is_low_stock)

    def test_discounted_price(self):
        """Test discounted price calculation"""
        product = Product.objects.create(
            name="Test Product",
            category=self.category,
            unit_cost=50.00,
            least_selling_price=70.00,
            wholesale_price=80.00,
            retail_price=100.00,
            discount_percent=10.00
        )
        
        # 10% discount on 100.00 should be 90.00
        self.assertEqual(product.discounted_price, 90.00)

    def test_available_stock(self):
        """Test available stock calculation with pack size"""
        product = Product.objects.create(
            name="Test Product",
            category=self.category,
            unit_cost=50.00,
            least_selling_price=70.00,
            wholesale_price=80.00,
            retail_price=100.00,
            quantity=10,
            pack_size=6
        )
        
        # 10 packs * 6 units per pack = 60 units
        self.assertEqual(product.available_stock, 60)


class StockTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(
            name="Test Product",
            category=self.category,
            unit_cost=50.00,
            least_selling_price=70.00,
            wholesale_price=80.00,
            retail_price=100.00
        )

    def test_stock_creation(self):
        """Test stock entry creation"""
        stock = Stock.objects.create(
            product=self.product,
            batch_no="BATCH001",
            quantity=100,
            unit_cost=45.00,
            location="Shelf A1"
        )
        
        self.assertEqual(stock.product, self.product)
        self.assertEqual(stock.batch_no, "BATCH001")
        self.assertEqual(stock.quantity, 100)

    def test_expiry_detection(self):
        """Test expiry date detection"""
        from datetime import date, timedelta
        
        # Create expired stock
        expired_stock = Stock.objects.create(
            product=self.product,
            batch_no="EXPIRED001",
            quantity=50,
            unit_cost=45.00,
            expiry_date=date.today() - timedelta(days=1)
        )
        
        # Create non-expired stock
        fresh_stock = Stock.objects.create(
            product=self.product,
            batch_no="FRESH001",
            quantity=50,
            unit_cost=45.00,
            expiry_date=date.today() + timedelta(days=30)
        )
        
        self.assertTrue(expired_stock.is_expired)
        self.assertFalse(fresh_stock.is_expired)

    def test_days_to_expiry(self):
        """Test days to expiry calculation"""
        from datetime import date, timedelta
        
        stock = Stock.objects.create(
            product=self.product,
            batch_no="EXPIRING001",
            quantity=50,
            unit_cost=45.00,
            expiry_date=date.today() + timedelta(days=10)
        )
        
        self.assertEqual(stock.days_to_expiry, 10)