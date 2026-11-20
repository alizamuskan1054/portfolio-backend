from django.db import migrations, models
import django.db.models.functions.text


class Migration(migrations.Migration):

    dependencies = [
        ('portfolios', '0007_portfolio_favicon'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='portfolio',
            name='unique_active_portfolio_per_client',
        ),
        migrations.AddConstraint(
            model_name='portfolio',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower('slug'), name='unique_portfolio_slug_ci'),
        ),
    ]
