from setuptools import setup, find_packages

setup(
    name='cloudpub',
    description='Services for publishing products in cloud environments',
    version='1.0.0',
    keywords='stratosphere cloudpub cloudpublish',
    author='Jonathan Gangi',
    author_email='jgangi@redhat.com',
    url='https://gitlab.cee.redhat.com/stratosphere/cloudpub',
    license='GPLv3+',
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    install_requires=[
        'attrs',
        'deepdiff',
        'requests',
        'tenacity',
        "boto3>=1.34.117",
    ],
    zip_safe=False,
)
