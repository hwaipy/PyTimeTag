import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()
version = '4.0.0b1'

setuptools.setup(
    name='pytimetag',
    version=version,
    author='Hwaipy',
    author_email='hwaipy@gmail.com',
    description='A data processing lib for TimeTag.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='GPL-3.0-only',
    url='https://github.com/hwaipy/PyTimeTag',
    keywords=['timetag', 'physics'],
    packages=setuptools.find_packages(exclude=("tests", "tests.*")),
    include_package_data=False,
    package_data={
        "pytimetag.gui": ["webui_dist/*", "webui_dist/assets/*"],
    },
    install_requires=[
        'numpy>=1.25',  # NumPy 2.x recommended
        'msgpack',
        'numba',
        'rich',
        'duckdb',
        'tzdata',
        'fastapi',
        'uvicorn',
        'celery',
        'redis',
        'websockets',
        'wsproto',
    ],
    extras_require={
        'swabian': [
            'Swabian-TimeTagger',
        ],
    },
    entry_points={
        'console_scripts': [
            'pytimetag=pytimetag.__main__:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
    ],
    python_requires='>=3.9',
)
