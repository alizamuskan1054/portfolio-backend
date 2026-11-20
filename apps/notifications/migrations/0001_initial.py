import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('portfolios', '0008_portfolio_multi_per_client_slug_ci'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kind', models.CharField(choices=[('contact_message', 'Contact message'), ('portfolio_created', 'Portfolio created'), ('portfolio_deleted', 'Portfolio deleted'), ('portfolio_published', 'Portfolio published'), ('portfolio_unpublished', 'Portfolio unpublished'), ('portal_activated', 'Portal activated')], max_length=40)),
                ('title', models.CharField(max_length=255)),
                ('body', models.TextField(blank=True, default='')),
                ('portfolio_title', models.CharField(blank=True, default='', max_length=255)),
                ('is_read', models.BooleanField(default=False)),
                ('portfolio', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='portfolios.portfolio')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'notifications',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', 'is_read'], name='notif_recipient_read_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', '-created_at'], name='notif_recipient_created_idx'),
        ),
    ]
