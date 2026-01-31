"""
API endpoint tests for BizPos
"""
import pytest
from decimal import Decimal
from rest_framework import status
from apps.products.models import Category, Product, Stock, StockMovement


@pytest.mark.django_db
class TestCategoryAPI:
    """Test Category API endpoints"""
    
    def test_list_categories(self, api_client, category):
        """Test listing categories"""
        response = api_client.get('/api/products/categories/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
    
    def test_create_category(self, api_client):
        """Test creating a category"""
        data = {
            'name': 'New Category',
            'description': 'Test description'
        }
        response = api_client.post('/api/products/categories/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Category'
    
    def test_retrieve_category(self, api_client, category):
        """Test retrieving a single category"""
        response = api_client.get(f'/api/products/categories/{category.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == category.name
    
    def test_update_category(self, api_client, category):
        """Test updating a category"""
        data = {'description': 'Updated description'}
        response = api_client.patch(f'/api/products/categories/{category.id}/', data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['description'] == 'Updated description'
    
    def test_delete_category(self, api_client):
        """Test deleting a category (should fail if has products)"""
        category = Category.objects.create(name='To Delete')
        response = api_client.delete(f'/api/products/categories/{category.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestProductAPI:
    """Test Product API endpoints"""
    
    def test_list_products(self, api_client, product):
        """Test listing products"""
        response = api_client.get('/api/products/products/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
    
    def test_create_product(self, api_client, category):
        """Test creating a product"""
        data = {
            'name': 'New Product',
            'category': category.id,
            'unit_cost': '100.00',
            'least_selling_price': '120.00',
            'wholesale_price': '150.00',
            'retail_price': '180.00',
            'reorder_level': 10
        }
        response = api_client.post('/api/products/products/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Product'
        
        # Verify product was created with auto-generated SKU
        product = Product.objects.get(name='New Product')
        assert product.sku
        assert len(product.sku) == 12  # XXX-XXX-0001 format
    
    def test_retrieve_product(self, api_client, product):
        """Test retrieving a single product"""
        response = api_client.get(f'/api/products/products/{product.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == product.name
        assert 'stock_entries' in response.data
        assert 'recent_movements' in response.data
    
    def test_update_product(self, api_client, product):
        """Test updating a product"""
        data = {'retail_price': '200.00'}
        response = api_client.patch(f'/api/products/products/{product.id}/', data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['retail_price'] == '200.00'
    
    def test_delete_product(self, api_client, product):
        """Test deleting a product"""
        response = api_client.delete(f'/api/products/products/{product.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestStockAPI:
    """Test Stock API endpoints"""
    
    def test_list_stock(self, api_client, stock_entry):
        """Test listing stock entries"""
        response = api_client.get('/api/products/stock/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
    
    def test_create_stock(self, api_client, product):
        """Test creating a stock entry"""
        data = {
            'product': product.id,
            'batch_no': 'NEW-BATCH',
            'quantity': 50,
            'unit_cost': '100.00',
            'location': 'Warehouse B'
        }
        response = api_client.post('/api/products/stock/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['batch_no'] == 'NEW-BATCH'
    
    def test_retrieve_stock(self, api_client, stock_entry):
        """Test retrieving a single stock entry"""
        response = api_client.get(f'/api/products/stock/{stock_entry.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['batch_no'] == stock_entry.batch_no


@pytest.mark.django_db
class TestStockOperationsAPI:
    """Test stock operation endpoints"""
    
    def test_add_stock_endpoint(self, api_client, product):
        """Test adding stock via API"""
        data = {
            'quantity': 50,
            'unit_cost': '100.00',
            'batch_no': 'API-BATCH-001',
            'reference': 'PO-001',
            'note': 'Test stock addition'
        }
        response = api_client.post(f'/api/products/products/{product.id}/add_stock/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert 'new_total_quantity' in response.data
        assert response.data['new_total_quantity'] == 50
        
        # Verify product quantity updated
        product.refresh_from_db()
        assert product.quantity == 50
    
    def test_remove_stock_endpoint(self, api_client, product):
        """Test removing stock via API"""
        # First add some stock
        product.add_stock(100, Decimal('100.00'), 'BATCH001')
        
        data = {
            'quantity': 30,
            'reference': 'SALE-001',
            'note': 'Test sale',
            'use_fifo': True
        }
        response = api_client.post(f'/api/products/products/{product.id}/remove_stock/', data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['new_total_quantity'] == 70
        
        # Verify product quantity updated
        product.refresh_from_db()
        assert product.quantity == 70
    
    def test_remove_stock_insufficient(self, api_client, product):
        """Test removing more stock than available"""
        product.add_stock(20, Decimal('100.00'), 'BATCH001')
        
        data = {
            'quantity': 50,
            'reference': 'SALE-001'
        }
        response = api_client.post(f'/api/products/products/{product.id}/remove_stock/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    def test_adjust_stock_endpoint(self, api_client, product):
        """Test adjusting stock via API"""
        product.add_stock(50, Decimal('100.00'), 'BATCH001')
        
        data = {
            'new_total_quantity': 75,
            'reference': 'ADJ-001',
            'note': 'Physical count adjustment'
        }
        response = api_client.post(f'/api/products/products/{product.id}/adjust_stock/', data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['new_total_quantity'] == 75
        
        # Verify product quantity updated
        product.refresh_from_db()
        assert product.quantity == 75
    
    def test_get_product_movements(self, api_client, product):
        """Test getting movements for a product"""
        # Create some movements
        product.add_stock(50, Decimal('100.00'), 'BATCH001')
        product.remove_stock(10, reference='SALE-001')
        
        response = api_client.get(f'/api/products/products/{product.id}/movements/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2


@pytest.mark.django_db
class TestStockMovementAPI:
    """Test StockMovement API endpoints"""
    
    def test_list_movements(self, api_client, product):
        """Test listing all movements"""
        # Create some movements
        product.add_stock(50, Decimal('100.00'), 'BATCH001')
        
        response = api_client.get('/api/products/stock-movements/')
        assert response.status_code == status.HTTP_200_OK
        # Response might be paginated, check for results or direct list
        if isinstance(response.data, dict) and 'results' in response.data:
            assert len(response.data['results']) >= 1
        else:
            assert len(response.data) >= 1
    
    def test_retrieve_movement(self, api_client, product):
        """Test retrieving a single movement"""
        stock = product.add_stock(50, Decimal('100.00'), 'BATCH001')
        movement = product.movements.first()
        
        response = api_client.get(f'/api/products/stock-movements/{movement.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['movement_type'] == 'IN'
    
    def test_movement_summary(self, api_client, product):
        """Test movement summary endpoint"""
        # Create various movements
        product.add_stock(100, Decimal('100.00'), 'BATCH001')
        product.remove_stock(30, reference='SALE-001')
        product.adjust_stock(80, reference='ADJ-001')
        
        response = api_client.get('/api/products/stock-movements/summary/')
        assert response.status_code == status.HTTP_200_OK
        assert 'total_movements' in response.data
        assert 'stock_in_total' in response.data
        assert 'stock_out_total' in response.data
        assert 'net_quantity' in response.data
    
    def test_filter_movements_by_type(self, api_client, product):
        """Test filtering movements by type"""
        product.add_stock(50, Decimal('100.00'), 'BATCH001')
        product.remove_stock(10, reference='SALE-001')
        
        response = api_client.get('/api/products/stock-movements/?movement_type=IN')
        assert response.status_code == status.HTTP_200_OK
        # Handle paginated response
        data = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        for movement in data:
            assert movement['movement_type'] == 'IN'
    
    def test_filter_movements_by_product(self, api_client, product, category):
        """Test filtering movements by product"""
        # Create another product
        product2 = Product.objects.create(
            name='Product 2',
            category=category,
            unit_cost=Decimal('50.00'),
            least_selling_price=Decimal('60.00'),
            wholesale_price=Decimal('70.00'),
            retail_price=Decimal('80.00')
        )
        
        product.add_stock(50, Decimal('100.00'), 'BATCH001')
        product2.add_stock(30, Decimal('50.00'), 'BATCH002')
        
        response = api_client.get(f'/api/products/stock-movements/?product={product.id}')
        assert response.status_code == status.HTTP_200_OK
        # Handle paginated response
        data = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        for movement in data:
            assert movement['product'] == product.id


@pytest.mark.django_db
class TestAPIValidation:
    """Test API validation"""
    
    def test_create_product_invalid_pricing(self, api_client, category):
        """Test that invalid pricing hierarchy is rejected"""
        data = {
            'name': 'Invalid Product',
            'category': category.id,
            'unit_cost': '200.00',  # Higher than retail!
            'least_selling_price': '120.00',
            'wholesale_price': '150.00',
            'retail_price': '180.00'
        }
        response = api_client.post('/api/products/products/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_add_stock_missing_unit_cost(self, api_client, product):
        """Test that unit_cost is required for add_stock"""
        data = {
            'quantity': 50,
            # Missing unit_cost
        }
        response = api_client.post(f'/api/products/products/{product.id}/add_stock/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_adjust_stock_missing_new_quantity(self, api_client, product):
        """Test that new_total_quantity is required for adjust_stock"""
        data = {
            'reference': 'ADJ-001'
            # Missing new_total_quantity
        }
        response = api_client.post(f'/api/products/products/{product.id}/adjust_stock/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
