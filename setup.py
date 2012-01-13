#!/usr/bin/env python

from setuptools import setup

try:  # Python 3.x
    from distutils.command.build_py import build_py_2to3 as build_py
except ImportError:  # Python 2.x
    from distutils.command.build_py import build_py

setup(name='Radio Astronomy Data Cube Utilities',
      version='0.2',
      author='Braden MacDonald',
      author_email='braden@bradenmacdonald.com',
      packages=['astrocube'],
      provides=['astrocube'],
      scripts=['astrocubeview.py'],
      requires=['numpy','pywcs','scipy.stats'],
      keywords=['Scientific/Engineering'],
     )
