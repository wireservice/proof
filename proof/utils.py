#!/usr/bin/env python

"""
This module contains common utilities used in proof.
"""

from functools import wraps

def memoize(func):
    """
    Dead-simple memoize decorator for instance methods that take no arguments.
    """
    memo = None

    @wraps(func)
    def wrapper(self):
        if memo is not None:
            return memo

        return func(self)

    return wrapper
