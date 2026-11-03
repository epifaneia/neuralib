# The librarian reads the whole catalog in one call: no vectors, no second pass.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0005_two_passes'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='book',
            name='book_embedding_hnsw',
        ),
        migrations.RemoveField(
            model_name='book',
            name='embedding',
        ),
        migrations.RemoveField(
            model_name='book',
            name='embedding_hash',
        ),
        migrations.RemoveField(
            model_name='librariananswer',
            name='knowledge_dropped',
        ),
        migrations.RemoveField(
            model_name='librariananswer',
            name='knowledge_failed',
        ),
        migrations.AlterField(
            model_name='librariananswer',
            name='dropped',
            field=models.PositiveSmallIntegerField(default=0, help_text='Picks the check removed (not in the catalog, no reason, quote not in the summary, repeated or over the limit).'),
        ),
        migrations.AlterField(
            model_name='librariananswer',
            name='knowledge_picks',
            field=models.JSONField(default=list, help_text='From what the model knows, unchecked: ids of the books recommended, in order.'),
        ),
        migrations.AlterField(
            model_name='librariananswer',
            name='picks',
            field=models.JSONField(default=list, help_text='From their summaries, with a checked quote: ids of the books recommended, in order.'),
        ),
    ]
