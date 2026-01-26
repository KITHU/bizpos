from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid
from datetime import datetime
from .constants import UNIT_CHOICES
import logging

logger = logging.getLogger(__name__)


class ProductSKUSequence(models.Model):
    """Stores the last sequence number used for each SKU prefix."""
    prefix = models.CharField(max_length=10, unique=True)  # e.g., "ELE-SP"
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.prefix}: {self.last_number}"


def generate_sku(category_name="GEN", product_name="PRD"):
    """
    Generate SKU based on category and product name using a sequence table.
    Format: CAT-PRD-0001
    Safe for concurrency and very fast.
    """
    # Helper to generate prefix
    def prefix(name):
        words = name.split()
        first = words[0][:3].upper()
        second = words[1][:2].upper() if len(words) > 1 else ''
        return (first + second).ljust(3, 'X')  # pad to at least 3 letters

    cat_prefix = prefix(category_name)
    prod_abbr = prefix(product_name)
    sku_prefix = f"{cat_prefix}-{prod_abbr}"

    try:
        with transaction.atomic():
            seq, created = ProductSKUSequence.objects.select_for_update().get_or_create(
                prefix=sku_prefix
            )
            seq.last_number += 1
            seq.save()
            sku_number = str(seq.last_number).zfill(4)
            return f"{sku_prefix}-{sku_number}"
    except Exception as e:
        logger.error(f"Failed to generate SKU: {e}")
        return f"SKU-{uuid.uuid4().hex[:8].upper()}-{datetime.now().strftime('%H%M%S')}"


class TimestampedModel(models.Model):
    """Abstract base model with timestamp fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimestampedModel):
    """Product categories for organization."""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(TimestampedModel):
    """Product master data with pricing, inventory, and settings."""
    # Identifiers
    sku = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        blank=True,
        help_text="Internal Stock Keeping Unit - auto-generated if not provided"
    )
    barcode = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        help_text="Product barcode - optional but must be unique if provided"
    )

    # Basic info
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')

    # Pricing
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost price per unit")
    least_selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2)
    retail_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Inventory basics
    quantity = models.IntegerField(default=0, help_text="Current stock quantity")
    reorder_level = models.IntegerField(default=10, help_text="Minimum stock level for reorder")
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='pcs')
    pack_size = models.IntegerField(default=1, help_text="Number of units in one pack")

    # Settings
    taxable = models.BooleanField(default=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_special = models.BooleanField(default=False)
    is_online = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Product"
        verbose_name_plural = "Products"
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_active', 'category']),
            models.Index(fields=['quantity']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(unit_cost__gte=0) &
                      models.Q(least_selling_price__gte=0) &
                      models.Q(wholesale_price__gte=0) &
                      models.Q(retail_price__gte=0),
                name='prices_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(pack_size__gt=0),
                name='pack_size_positive'
            ),
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='quantity_non_negative'
            ),
        ]

    def save(self, *args, **kwargs):
        """Override save to auto-generate SKU if not provided."""
        if not self.sku:
            self.sku = generate_sku(
                category_name=self.category.name if self.category else "GEN",
                product_name=self.name
            )
        super().save(*args, **kwargs)

    def clean(self):
        """Validate pricing hierarchy and non-negative prices."""
        super().clean()
        prices = [self.unit_cost, self.least_selling_price, self.wholesale_price, self.retail_price]
        if any(p < 0 for p in prices):
            raise ValidationError("All prices must be non-negative.")
        if not (self.unit_cost <= self.least_selling_price <= self.wholesale_price <= self.retail_price):
            raise ValidationError("Pricing hierarchy violated: unit_cost <= least_selling_price <= wholesale_price <= retail_price.")

    def __str__(self):
        barcode_str = f" | {self.barcode}" if self.barcode else ""
        category_str = f" | {self.category.name}" if self.category else ""
        return f"{self.name} ({self.sku}){category_str}{barcode_str}"

    @property
    def is_low_stock(self):
        """Check if product is below reorder level."""
        return self.quantity <= self.reorder_level

    @property
    def profit_margin(self):
        """Calculate profit margin percentage based on retail price."""
        if self.unit_cost > 0:
            return ((self.retail_price - self.unit_cost) / self.unit_cost) * 100
        return 0

    @property
    def available_stock(self):
        """Stock considering pack size."""
        return self.quantity * self.pack_size

    @property
    def discounted_price(self):
        """Price after discount applied."""
        return round(self.retail_price * (1 - self.discount_percent / 100), 2)

    @classmethod
    def generate_preview_sku(cls, category_name=None, product_name=None):
        """Preview next SKU without incrementing sequence."""
        if not category_name:
            category_name = "GEN"
        if not product_name:
            product_name = "PRD"

        def prefix(name):
            words = name.split()
            first = words[0][:3].upper()
            second = words[1][:2].upper() if len(words) > 1 else ''
            return (first + second).ljust(3, 'X')

        cat_prefix = prefix(category_name)
        prod_abbr = prefix(product_name)
        sku_prefix = f"{cat_prefix}-{prod_abbr}"

        try:
            seq = ProductSKUSequence.objects.get(prefix=sku_prefix)
            next_number = seq.last_number + 1
        except ProductSKUSequence.DoesNotExist:
            next_number = 1

        return f"{sku_prefix}-{str(next_number).zfill(4)}"


class Stock(TimestampedModel):
    """Simple stock tracking with batch and expiry information."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_entries')
    batch_no = models.CharField(max_length=100, help_text="Batch/Lot number")
    expiry_date = models.DateField(null=True, blank=True, help_text="Product expiry date")
    quantity = models.IntegerField(help_text="Quantity in this batch")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost per unit for this batch")
    location = models.CharField(max_length=200, blank=True, help_text="Storage location")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['product', 'batch_no']
        ordering = ['expiry_date', 'created_at']
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['expiry_date']),
            models.Index(fields=['batch_no']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(quantity__gte=0), name='stock_quantity_non_negative'),
            models.CheckConstraint(check=models.Q(unit_cost__gte=0), name='stock_unit_cost_non_negative'),
        ]

    def __str__(self):
        expiry_str = f" | Exp: {self.expiry_date}" if self.expiry_date else ""
        return f"{self.product.name} - Batch: {self.batch_no} ({self.quantity}){expiry_str}"

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()

    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return None
        delta = self.expiry_date - timezone.now().date()
        return delta.days
