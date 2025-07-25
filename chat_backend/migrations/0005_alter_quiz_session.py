# Generated by Django 5.2.4 on 2025-07-06 09:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat_backend', '0004_chatmessage_quiz'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quiz',
            name='session',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='quizzes', to='chat_backend.chatsession'),
            preserve_default=False,
        ),
    ]
