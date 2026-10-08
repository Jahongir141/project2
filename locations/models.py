from django.db import models


class Section(models.Model):
    name = models.CharField("Nomi", max_length=60, unique=True)
    sort_order = models.PositiveIntegerField("Tartib", default=0, db_index=True)
    active = models.BooleanField("Faol", default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Sektor"
        verbose_name_plural = "Sektorlar"

    def __str__(self):
        return self.name


class DiningTable(models.Model):
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="tables", verbose_name="Sektor")
    name = models.CharField("Joy nomi/raqami", max_length=20)
    capacity = models.PositiveSmallIntegerField("Sig‘im", default=4)
    active = models.BooleanField("Faol", default=True)
    sort_order = models.PositiveIntegerField("Tartib", default=0)

    class Meta:
        ordering = ["section__sort_order", "sort_order", "id"]
        verbose_name = "O‘tirish joyi"
        verbose_name_plural = "O‘tirish joylari"
        constraints = [
            models.UniqueConstraint(fields=["section", "name"], name="uniq_table_name_per_section"),
        ]
        indexes = [models.Index(fields=["section", "active", "sort_order"])]

    @property
    def label(self):
        suffix = "-joy" if self.name.isdigit() else ""
        return f"{self.section.name} — {self.name}{suffix}"

    def __str__(self):
        return f"{self.section.name} → {self.name}"
