from django.core.management.base import BaseCommand
from apps.products.models import Product, Category


class Command(BaseCommand):
    help = 'Generate example SKUs using the sequence-based method'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            type=str,
            default='Electronics',
            help='Category name for testing'
        )
        parser.add_argument(
            '--product',
            type=str,
            default='Smartphone',
            help='Product name for testing'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='Number of SKU examples to generate'
        )

    def handle(self, *args, **options):
        category_name = options['category']
        product_name = options['product']
        count = options['count']
        
        self.stdout.write(
            self.style.SUCCESS(f'Generating {count} SKU examples for:')
        )
        self.stdout.write(f'Category: {category_name}')
        self.stdout.write(f'Product: {product_name}')
        self.stdout.write('-' * 50)
        
        # Show what the next few SKUs would look like
        for i in range(count):
            try:
                sku = Product.generate_preview_sku(
                    category_name=category_name,
                    product_name=product_name
                )
                self.stdout.write(f'Preview {i+1}: {sku}')
                
                # Actually generate one to increment the sequence
                if i == 0:  # Only create the first one
                    from apps.products.models import generate_sku
                    actual_sku = generate_sku(category_name, product_name)
                    self.stdout.write(f'Generated: {actual_sku}')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error generating SKU: {str(e)}')
                )
        
        self.stdout.write('-' * 50)
        
        # Show some examples with different category/product combinations
        examples = [
            ('Food & Beverage', 'Coca Cola'),
            ('Electronics', 'iPhone Pro Max'),
            ('Clothing', 'T-Shirt'),
            ('Books', 'Python Programming'),
            ('Home Garden', 'Plant Pot'),
        ]
        
        self.stdout.write('Example SKUs for different products:')
        for cat, prod in examples:
            try:
                sku = Product.generate_preview_sku(cat, prod)
                self.stdout.write(f'{cat} + {prod} = {sku}')
            except Exception as e:
                self.stdout.write(f'Error: {e}')
        
        self.stdout.write('-' * 50)
        self.stdout.write(
            self.style.SUCCESS('SKU generation examples completed!')
        )