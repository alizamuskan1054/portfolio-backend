from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='kind',
            field=models.CharField(choices=[('contact_message', 'Contact message'), ('portfolio_created', 'Portfolio created'), ('portfolio_deleted', 'Portfolio deleted'), ('portfolio_published', 'Portfolio published'), ('portfolio_unpublished', 'Portfolio unpublished'), ('portal_activated', 'Portal activated'), ('portal_welcome', 'Portal welcome')], max_length=40),
        ),
    ]
