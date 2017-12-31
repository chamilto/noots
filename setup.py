from setuptools import setup, find_packages

setup(
    name='noots',
    version='0.1',
    author='chamilto',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'noots = noots:main',
        ],
    },
)
