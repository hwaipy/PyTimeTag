import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()
version = '1.0.1'

setuptools.setup(
    name='pytimetag',
    version=version,
    author='Hwaipy',
    author_email='hwaipy@gmail.com',
    description='A data processing lib for TimeTag.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='gpl-3.0',
    # url='https://github.com/hwaipy/InteractionFreePy',
    # download_url='https://github.com/hwaipy/InteractionFreePy/archive/v{}.tar.gz'.format(version),
    keywords=['timetag', 'physics'],
    packages=setuptools.find_packages(),
    install_requires=[
        'numba',
        'numpy',
        'msgpack'
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    python_requires='>=3.6',
)
