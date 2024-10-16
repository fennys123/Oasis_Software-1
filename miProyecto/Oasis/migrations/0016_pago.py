# Generated by Django 5.1.1 on 2024-10-15 14:22

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Oasis', '0015_mesa_total_ganancia_venta_total_ganancia_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Pago',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_pagado', models.DecimalField(decimal_places=2, max_digits=10)),
                ('fecha_pago', models.DateTimeField(auto_now=True)),
                ('mesa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='Oasis.mesa')),
            ],
        ),
    ]
