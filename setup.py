import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()
version = '3.0.4'

setuptools.setup(
    name='pytimetag',
    version=version,
    author='Hwaipy',
    author_email='hwaipy@gmail.com',
    description='A data processing lib for TimeTag.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='gpl-3.0',
    url='https://github.com/hwaipy/PyTimeTag',
    keywords=['timetag', 'physics'],
    packages=setuptools.find_packages(),
    install_requires=[
        'numpy>=1.25',  # NumPy 2.x recommended
        'msgpack',
        'numba',
        'rich'
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
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
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
