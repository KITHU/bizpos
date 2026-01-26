# 💼 BizPos

**BizPos** is a modern, cross-platform Point of Sale (POS) and Inventory Management system designed for businesses of all sizes.  
Built with **Django REST Framework** for the backend and designed to work seamlessly on **web** and **mobile** platforms.

---

## 🚀 Features

- 📦 **Inventory Management** with batch tracking and expiry dates
- 🏷️ **Auto-generated SKUs** using sequence-based system (CAT-PRD-0001)
- 💰 **Comprehensive Pricing** (unit cost, least selling, wholesale, retail)
- 📊 **Profit Margin Calculation** and discount support
- 🔍 **Low Stock Detection** with reorder levels
- 📅 **Expiry Tracking** with days-to-expiry calculation
- 🏪 **Location-based Stock** management
- 🔐 **Data Validation** with pricing hierarchy constraints
- 📱 **REST API** with filtering, search, and pagination
- 🎛️ **Admin Interface** with comprehensive management tools

---

## 🛠️ Tech Stack

### Backend:
- **Django 5.2** – Python web framework
- **Django REST Framework** – RESTful API toolkit
- **SQLite** – Database (development)
- **PostgreSQL** *(recommended for production)*
- **Docker** *(optional)* – Containerization
- **Redis** *(optional)* – Caching / background tasks

### Frontend (planned):
- **Web** – React / Vue / Svelte (TBD)
- **Mobile** – Flutter or React Native

---

## 📂 Project Structure

```bash
BizPos/
├── bizpos/               # Main project configuration
│   ├── __init__.py
│   ├── settings.py       # Django settings with DRF config
│   ├── urls.py           # URL routing
│   ├── wsgi.py           # WSGI config
│   └── asgi.py           # ASGI config
├── apps/                 # Django apps
│   └── products/         # Products app
│       ├── models.py     # Category, Product, Stock, ProductSKUSequence
│       ├── serializers.py # DRF serializers
│       ├── views.py      # API ViewSets
│       ├── urls.py       # API routing
│       ├── admin.py      # Admin interface
│       ├── tests.py      # Unit tests
│       ├── constants.py  # App constants
│       └── management/   # Management commands
│           └── commands/
│               └── generate_sku_examples.py
├── manage.py             # Django management script
├── db.sqlite3            # SQLite database
├── requirements.txt      # Python dependencies
└── README.md             # Project overview

```

---

## 🏁 Getting Started

### Prerequisites
- Python 3.10+
- pip or virtualenv

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd BizPos
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

7. **Access the application**
   - API: http://localhost:8000/
   - Admin Panel: http://localhost:8000/admin/

---

## 📡 API Documentation

### **Categories**
- `GET /api/products/categories/` - List categories
- `POST /api/products/categories/` - Create category
- `GET /api/products/categories/{id}/` - Get category details
- `PUT/PATCH /api/products/categories/{id}/` - Update category
- `DELETE /api/products/categories/{id}/` - Delete category

### **Products**
- `GET /api/products/products/` - List products (lightweight)
- `POST /api/products/products/` - Create product (auto-generates SKU)
- `GET /api/products/products/{id}/` - Get product details (with stock)
- `PUT/PATCH /api/products/products/{id}/` - Update product
- `DELETE /api/products/products/{id}/` - Delete product

### **Stock**
- `GET /api/products/stock/` - List stock entries
- `POST /api/products/stock/` - Create stock entry
- `GET /api/products/stock/{id}/` - Get stock details
- `PUT/PATCH /api/products/stock/{id}/` - Update stock
- `DELETE /api/products/stock/{id}/` - Delete stock

### **Features**
- **Filtering**: Filter by category, status, activity
- **Search**: Search across names, SKUs, descriptions
- **Ordering**: Sort by various fields
- **Pagination**: Built-in pagination support

---

## 🧪 Running Tests

```bash
python manage.py test
```

---

## 📝 License

This project is licensed under the MIT License.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 🏷️ SKU Generation System

The system uses a sequence-based SKU generation that's safe for concurrency:

### **Format**: `CAT-PRD-0001`
- **CAT**: First 3 letters of category (padded with X if needed)
- **PRD**: First 3 letters of product (padded with X if needed)  
- **0001**: 4-digit sequence number

### **Examples**:
```
Electronics + Smartphone = ELE-SMA-0001
Food Beverage + Coca Cola = FOO-COC-0001
Home Garden + Plant Pot = HOM-PLA-0001
```

### **Management Command**:
```bash
python manage.py generate_sku_examples --category="Electronics" --product="iPhone"
```

## 💰 Pricing System

Products support a comprehensive pricing hierarchy:
- **Unit Cost**: Cost price per unit
- **Least Selling Price**: Minimum selling price
- **Wholesale Price**: Bulk/wholesale price
- **Retail Price**: Regular selling price
- **Discount**: Percentage discount applied

**Validation**: `unit_cost ≤ least_selling_price ≤ wholesale_price ≤ retail_price`

## 📦 Stock Management

- **Batch Tracking**: Each stock entry has a unique batch number
- **Expiry Management**: Track expiry dates and calculate days to expiry
- **Location Tracking**: Optional location field for warehouse management
- **Automatic Calculations**: Total stock, available stock, expired stock

## 🔧 Development Commands

```bash
# Generate migrations
python manage.py makemigrations

# Apply migrations  
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Run tests
python manage.py test apps.products

# Generate SKU examples
python manage.py generate_sku_examples
```