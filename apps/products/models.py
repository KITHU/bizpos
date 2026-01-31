from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
import uuid
from datetime import datetime
from .constants import UNIT_CHOICES
import logging

logger = logging.getLogger(__name__)


class ProductSKUSequence(models.Model):
    """Stores the last sequence number used for each SKU prefix."""
    prefix = models.CharField(max_length=15, unique=True)  # e.g., "ELE-SP"
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
        result = first + second
        # Ensure exactly 3 characters
        if len(result) > 3:
            return result[:3]
        else:
            return result.ljust(3, 'X')

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
        max_length=20,  # Allow longer manual SKUs if needed
        unique=True, 
        db_index=True, 
        blank=True,
        help_text="Internal Stock Keeping Unit - auto-generated format: XXX-XXX-0001 (12 chars)"
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
                condition=models.Q(unit_cost__gte=0) &
                      models.Q(least_selling_price__gte=0) &
                      models.Q(wholesale_price__gte=0) &
                      models.Q(retail_price__gte=0),
                name='prices_non_negative'
            ),
            models.CheckConstraint(
                condition=models.Q(pack_size__gt=0),
                name='pack_size_positive'
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name='quantity_non_negative'
            ),
        ]

    def save(self, *args, **kwargs):
        """Override save to auto-generate SKU if not provided."""
        # Only auto-update quantity if this is a new product or if explicitly requested
        update_quantity = kwargs.pop('update_quantity', self.pk is None)
        
        if not self.sku:
            self.sku = generate_sku(
                category_name=self.category.name if self.category else "GEN",
                product_name=self.name
            )
        super().save(*args, **kwargs)
        
        # Update quantity after saving (only for new products by default)
        if update_quantity:
            self.update_quantity_from_stock()

    def update_quantity_from_stock(self):
        """Update product quantity based on active stock entries."""
        from django.db.models import Sum
        total = self.stock_entries.filter(is_active=True).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        if self.quantity != total:
            # Use update to avoid triggering save() again and prevent recursion
            Product.objects.filter(pk=self.pk).update(quantity=total)
            # Refresh the instance to reflect the updated quantity
            self.refresh_from_db(fields=['quantity'])

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
            result = first + second
            # Ensure exactly 3 characters
            if len(result) > 3:
                return result[:3]
            else:
                return result.ljust(3, 'X')

        cat_prefix = prefix(category_name)
        prod_abbr = prefix(product_name)
        sku_prefix = f"{cat_prefix}-{prod_abbr}"

        try:
            seq = ProductSKUSequence.objects.get(prefix=sku_prefix)
            next_number = seq.last_number + 1
        except ProductSKUSequence.DoesNotExist:
            next_number = 1

        return f"{sku_prefix}-{str(next_number).zfill(4)}"

    def add_stock(self, quantity, unit_cost, batch_no=None, expiry_date=None, 
                  location=None, reference="", note=""):
        """Add stock with automatic movement tracking."""
        from django.utils import timezone
        
        if batch_no is None:
            batch_no = f"BATCH-{timezone.now().strftime('%Y%m%d-%H%M%S')}"
        
        with transaction.atomic():
            # Create or update stock entry
            stock, created = Stock.objects.get_or_create(
                product=self,
                batch_no=batch_no,
                defaults={
                    'quantity': 0,
                    'unit_cost': unit_cost,
                    'expiry_date': expiry_date,
                    'location': location or '',
                }
            )
            
            # Don't update stock.quantity here - let StockMovement.save() handle it
            # This prevents double-counting
            
            # Create movement record - this will update stock.quantity automatically
            from django.apps import apps
            StockMovement = apps.get_model('products', 'StockMovement')
            StockMovement.objects.create(
                product=self,
                stock=stock,
                movement_type='IN',
                quantity=quantity,
                unit_cost=unit_cost,
                reference=reference,
                note=note or f"Stock added - Batch: {batch_no}"
            )
            
            # Refresh stock to get updated quantity
            stock.refresh_from_db()
            return stock

    def remove_stock(self, quantity, reference="", note="", use_fifo=True):
        """Remove stock with automatic movement tracking using FIFO."""
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        remaining_to_remove = quantity
        movements_created = []
        
        with transaction.atomic():
            # Get stock entries to remove from (FIFO order)
            if use_fifo:
                stock_entries = self.stock_entries.filter(
                    is_active=True, 
                    quantity__gt=0
                ).order_by('expiry_date', 'created_at')
            else:
                stock_entries = self.stock_entries.filter(
                    is_active=True, 
                    quantity__gt=0
                ).order_by('-created_at')
            
            for stock in stock_entries:
                if remaining_to_remove <= 0:
                    break
                
                # Calculate how much to remove from this batch
                remove_from_batch = min(remaining_to_remove, stock.quantity)
                
                # Create movement record
                from django.apps import apps
                StockMovement = apps.get_model('products', 'StockMovement')
                movement = StockMovement.objects.create(
                    product=self,
                    stock=stock,
                    movement_type='OUT',
                    quantity=-remove_from_batch,  # Negative for OUT
                    unit_cost=stock.unit_cost,
                    reference=reference,
                    note=note or f"Stock removed - Batch: {stock.batch_no}"
                )
                movements_created.append(movement)
                
                remaining_to_remove -= remove_from_batch
            
            if remaining_to_remove > 0:
                raise ValueError(f"Insufficient stock. Requested: {quantity}, Available: {quantity - remaining_to_remove}")
            
            return movements_created

    def adjust_stock(self, new_total_quantity, reference="", note=""):
        """Adjust total stock to a specific quantity."""
        current_quantity = self.quantity
        difference = new_total_quantity - current_quantity
        
        if difference == 0:
            return None
        
        with transaction.atomic():
            # For adjustments, we need to update stock batches
            # The movement will be created but won't auto-update stock since stock=None
            
            if difference > 0:
                # Positive adjustment - add to most recent batch or create new one
                recent_stock = self.stock_entries.filter(is_active=True).order_by('-created_at').first()
                
                from django.apps import apps
                StockMovement = apps.get_model('products', 'StockMovement')
                
                if recent_stock:
                    # Create movement linked to existing batch
                    movement = StockMovement.objects.create(
                        product=self,
                        stock=recent_stock,
                        movement_type='ADJUST',
                        quantity=difference,
                        unit_cost=recent_stock.unit_cost,
                        reference=reference,
                        note=note or f"Stock adjustment: {current_quantity} → {new_total_quantity}"
                    )
                else:
                    # Create new adjustment batch with movement
                    adj_stock = Stock.objects.create(
                        product=self,
                        batch_no=f"ADJ-{timezone.now().strftime('%Y%m%d-%H%M%S')}",
                        quantity=0,  # Start at 0, movement will update it
                        unit_cost=self.unit_cost,
                    )
                    movement = StockMovement.objects.create(
                        product=self,
                        stock=adj_stock,
                        movement_type='ADJUST',
                        quantity=difference,
                        unit_cost=self.unit_cost,
                        reference=reference,
                        note=note or f"Stock adjustment: {current_quantity} → {new_total_quantity}"
                    )
            else:
                # Negative adjustment - remove using FIFO
                # remove_stock creates its own movements
                self.remove_stock(abs(difference), reference=reference, note=note or "Stock adjustment")
                movement = None
            
            return movement


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
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name='stock_quantity_non_negative'),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name='stock_unit_cost_non_negative'),
        ]

    def save(self, *args, **kwargs):
        """Override save to update product quantity only when not called from StockMovement."""
        # Check if this save is being called from a StockMovement operation
        skip_product_update = kwargs.pop('skip_product_update', False)
        
        super().save(*args, **kwargs)
        
        # Only update product quantity if not called from StockMovement
        if not skip_product_update:
            self.product.update_quantity_from_stock()

    def delete(self, *args, **kwargs):
        """Override delete to update product quantity."""
        product = self.product
        super().delete(*args, **kwargs)
        # Update the related product's quantity after deletion
        product.update_quantity_from_stock()

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


class StockMovement(TimestampedModel):
    """Track all stock movements for audit trail and inventory management."""
    
    # Movement Types
    IN = 'IN'
    OUT = 'OUT'
    ADJUST = 'ADJUST'
    TRANSFER = 'TRANSFER'
    RETURN = 'RETURN'
    DAMAGE = 'DAMAGE'
    
    MOVEMENT_TYPE_CHOICES = [
        (IN, 'Stock In'),
        (OUT, 'Stock Out'),
        (ADJUST, 'Adjustment'),
        (TRANSFER, 'Transfer'),
        (RETURN, 'Return'),
        (DAMAGE, 'Damage/Loss'),
    ]
    
    # Core fields
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='movements'
    )
    stock = models.ForeignKey(
        Stock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
        help_text="Related stock batch (if applicable)"
    )
    
    # Movement details
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPE_CHOICES)
    quantity = models.IntegerField(help_text="Positive for IN, negative for OUT")
    unit_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Cost per unit for this movement"
    )
    
    # Reference and tracking
    reference = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Invoice no, order id, POS transaction, etc."
    )
    note = models.TextField(blank=True, help_text="Additional notes or reason")
    
    # Optional user tracking (if you have user authentication)
    # user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'movement_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['movement_type', 'created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity=0),
                name='movement_quantity_not_zero'
            ),
        ]

    def clean(self):
        """Validate movement data."""
        super().clean()
        
        # Validate quantity based on movement type
        if self.movement_type == self.IN and self.quantity <= 0:
            raise ValidationError("Stock IN movements must have positive quantity")
        elif self.movement_type == self.OUT and self.quantity >= 0:
            raise ValidationError("Stock OUT movements must have negative quantity")

    def save(self, *args, **kwargs):
        """Override save to update stock and product quantities."""
        self.clean()
        
        with transaction.atomic():
            super().save(*args, **kwargs)
            
            # Update stock entry if specified
            if self.stock:
                self.stock.quantity += self.quantity
                if self.stock.quantity < 0:
                    raise ValidationError(f"Stock batch {self.stock.batch_no} would have negative quantity")
                # Save stock without triggering product update (we'll do it once at the end)
                self.stock.save(skip_product_update=True)
            
            # Update product quantity once at the end
            self.product.update_quantity_from_stock()

    def __str__(self):
        sign = "+" if self.quantity > 0 else ""
        return f"{self.product.sku} | {self.get_movement_type_display()} | {sign}{self.quantity}"

    @property
    def total_value(self):
        """Calculate total value of this movement."""
        if self.unit_cost:
            return abs(self.quantity) * self.unit_cost
        return None
