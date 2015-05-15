from django.db import models


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey('Recipe')
    ingredient = models.ForeignKey('Ingredient')
    quantity = models.IntegerField()


class Recipe(models.Model):
    name = models.CharField(max_length=32)
    category = models.ForeignKey('Category', null=True)
    ingredients = models.ManyToManyField('Ingredient', through=RecipeIngredient)


class Cookware(models.Model):
    name = models.CharField(max_length=32)
    recipes = models.ManyToManyField('Recipe')


class Ingredient(models.Model):
    name = models.CharField(max_length=32)
    recipes = models.ManyToManyField('Recipe', through=RecipeIngredient)


class Category(models.Model):
    name = models.CharField(max_length=32)
