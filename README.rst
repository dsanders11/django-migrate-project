========================
 django-migrate-project
========================

.. image:: https://img.shields.io/badge/license-MIT-blue.svg
   :alt: License
   :target: https://raw.githubusercontent.com/dsanders11/django-migrate-project/master/LICENSE

.. image:: https://travis-ci.org/dsanders11/django-migrate-project.svg?branch=master
   :alt: Build Status
   :target: https://travis-ci.org/dsanders11/django-migrate-project

.. image:: https://img.shields.io/pypi/v/django-migrate-project.svg
   :alt: Latest PyPI version
   :target: https://pypi.python.org/pypi/django-migrate-project/

.. image:: https://coveralls.io/repos/dsanders11/django-migrate-project/badge.svg?branch=master
   :alt: Coverage
   :target: https://coveralls.io/r/dsanders11/django-migrate-project?branch=master

`Django`_ management commands for project-wide (editable) migrations.

Overview
========

The django-migrate-project app aims to add management commands to make running
full project migrations more sane and controllable. The concept is pretty
simple: first collect any unapplied migrations into per-app migration files,
then review and modify as need be, and finally apply the migrations.

By staging and consolidating unapplied migrations in a way that they can be
edited and reviewed before applying, more confidence is gained that a rogue
migration won't damage production tables. The collected and consolidated
migrations are listed as replacements for the individual app migrations they
represent so once they have been applied everything is in the same state as if
the individual app migrations has been applied via 'migrate'.

Requirements
============

Requires Django 1.7+ and as such Python 2.7+ as well

Installation
============

Simply use `pip`_ to install::

    $ pip install django-migrate-project

To be of any use ``django-migrate-project`` must be added to the Django project
via ``INSTALLED_APPS`` in the project ``settings.py`` file::

    INSTALLED_APPS = (
        ...
        'django_migrate_project',
        ...
    )

Usage
=====

Two new management commands provide the core functionality. To gather up any
unapplied migrations for the project simply run::

    $ python manage.py collectmigrations

The default collection location is ``BASE_DIR/pending_migrations``. If the project's
``settings.py`` does not have a ``BASE_DIR`` then a directory path must be provided
using the ``--output-dir`` option.

The collected migrations are grouped per-app and have the filename format of
``<app_label>_project.py``. These files can be edited to taste in order to
change the migration, the only important bit is to keep the `replaces` and
``dependencies`` fields in the migration the same, as those allow the bookkeeping
to be kept accurate.

Collected migrations are applied via::

    $ python manage.py applymigrations

The default directory path is used again if possible, otherwise the path must
be provided via the ``--input-dir`` option.

Finally, migrations can be unapplied easily as well, returning the migration
state to what it was before by running::

    $ python manage.py applymigrations --unapply

Experimental
============

Starting with v0.2.0 there's also the capability to generate project-level
migrations as a way to capture monkey-patched models and other changes that
shouldn't create migrations in a third-party app.

To use this functionality, first create a top-level `migrations` directory
with a `__init__.py` file to make it a Python package. Then run the following
command to create any new project-level migrations (changes not present in
third-party app migrations)::

    $ python manage.py makeprojectmigrations

Assuming there are any migrations to generate, the top-level `migrations`
directory should now be populated and you can migrate the project using::

    $ python manage.py migrateproject

As with the `applymigrations` command, `migrateproject` also has an easy
unapply functionality::

    $ python manage.py migrateproject --unapply

While this functionality is well covered by tests it will remain 'experimental'
until it gets a bit more real world use.

Contributing
============

Contributions are welcome, just create a pull request or issue on the
`GitHub repository`_ for the project.

.. _`Django`: https://djangoproject.com/
.. _`GitHub repository`: https://github.com/dsanders11/django-migrate-project
.. _`pip`: https://pip.pypa.io/en/stable/
.. _`Python`: https://python.org/
