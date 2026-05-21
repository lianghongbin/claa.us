from django.db import migrations


def seed_categories(apps, schema_editor):
    Category = apps.get_model("finance", "Category")
    rows = [
        ("销售收入", "income", 10),
        ("其他收入", "income", 20),
        ("利息收入", "income", 30),
        ("办公费用", "expense", 10),
        ("差旅费用", "expense", 20),
        ("人力成本", "expense", 30),
        ("税费", "expense", 40),
        ("其他支出", "expense", 90),
    ]
    for name, kind, sort_order in rows:
        Category.objects.get_or_create(
            name=name,
            kind=kind,
            defaults={"sort_order": sort_order, "is_active": True},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, noop_reverse),
    ]
