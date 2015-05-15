""" Setup for django-migrate-project """

from setuptools import setup, find_packages

from django_migrate_project import __version__


setup(
    name="django-migrate-project",
    version=__version__,
    description="Django management commands for project-wide (editable) "
                "migrations.",
    long_description=open("README.rst", 'rb').read().decode('utf-8'),
    license="MIT",
    author="David Sanders",
    author_email="dsanders11@ucsbalum.com",
    url="https://github.com/dsanders11/django-migrate-project/",
    keywords="django migration database",
    packages=find_packages(exclude=("tests", "test_project")),
    install_requires=[
        "Django > 1.7"
    ],
    tests_require=['mock'],
    test_suite="runtests.run_tests",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Utilities",
        "Topic :: Database"
    ]
)
