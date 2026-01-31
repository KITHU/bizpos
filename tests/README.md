# BizPos Tests

This directory contains all tests for the BizPos application.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py          # Pytest fixtures and configuration
├── test_models.py       # Model unit tests
└── test_api.py          # API endpoint tests
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=apps --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_models.py
```

### Run specific test class
```bash
pytest tests/test_models.py::TestProduct
```

### Run specific test
```bash
pytest tests/test_models.py::TestProduct::test_create_product
```

### Run with verbose output
```bash
pytest -v
```

### Run tests by marker
```bash
pytest -m unit          # Run only unit tests
pytest -m api           # Run only API tests
pytest -m integration   # Run only integration tests
```

## Test Coverage

After running tests with coverage, open the HTML report:
```bash
open htmlcov/index.html
```

## Writing Tests

### Fixtures
Common fixtures are defined in `conftest.py`:
- `api_client` - REST framework API client
- `user` - Test user
- `category` - Test category
- `product` - Test product
- `product_with_stock` - Product with stock
- `stock_entry` - Stock entry

### Example Test
```python
import pytest
from apps.products.models import Product

@pytest.mark.django_db
class TestProduct:
    def test_create_product(self, category):
        product = Product.objects.create(
            name='Test Product',
            category=category,
            unit_cost=100.00,
            retail_price=150.00
        )
        assert product.name == 'Test Product'
```

## CI/CD

Tests run automatically on:
- Every push to any branch
- Pull requests to main, develop, or staging branches

The GitHub Actions workflow:
1. Sets up Python 3.10.12
2. Installs dependencies
3. Sets up MySQL database
4. Runs migrations
5. Runs tests with coverage
6. Uploads coverage reports

## Test Database

Tests use a separate test database that is:
- Created automatically before tests
- Destroyed after tests complete
- Isolated from your development database

## Markers

Available test markers:
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.django_db` - Tests that need database access
