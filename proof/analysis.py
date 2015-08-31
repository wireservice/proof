#!/usr/bin/env python

"""
This module contains the :class:`Analysis` class, which is used for creating
optimized, repeatable data processing workflows. An analysis can be created
from a function or any other callable object. Dependent analyses can then be
created using the :meth:`Analysis.then` method. Each function must accept a
``data`` argument, which is a :class:`dict` of data to be persisted between
analyses. Modifications made to ``data`` in the scope of one analysis will be
propogated to all dependent analyses.
"""

import bz2
from copy import deepcopy
from glob import glob
import hashlib
import inspect
import os

try:
    import cPickle as pickle
except ImportError: # pragma: no cover
    import pickle

from proof.utils import memoize

class Analysis(object):
    """
    An Analysis is a function whose source code fingerprint and output can be
    serialized to disk. When it is invoked again, if it's code has not changed
    the serialized output will be used rather than executing the code again.

    Implements a callback-like API so that Analyses can depend on one another.
    If a parent analysis changes then it and all it's children will be
    refreshed.

    :param func: A callable that implements the analysis. Must accept a `data`
        argument that is the state inherited from its ancestors analysis.
    :param cache_dir: Where to stored the cache files for this analysis.
    :param _parent: The parent analysis of this one, if any. For internal use
        only.
    """
    def __init__(self, func, cache_dir='.proof', _parent=None):
        self._name = func.__name__
        self._func = func
        self._parent = _parent
        self._cache_dir = cache_dir
        self._next_analyses = []

        self._registered_cache_paths = []

    @memoize
    def _trace(self):
        """
        Returns the sequence of Analysis instances that lead to this one.
        """
        if self._parent:
            return self._parent._trace() + [self]

        return [self]

    @memoize
    def _root(self):
        """
        Returns the root node of this Analysis' trace. (It may be itself.)
        """
        return self._trace()[0]

    @memoize
    def _fingerprint(self):
        """
        Generate a fingerprint for this analysis function.
        """
        hasher = hashlib.md5()

        trace = [analysis._name for analysis in self._trace()]
        hasher.update('\n'.join(trace).encode('utf-8'))

        source = inspect.getsource(self._func)
        hasher.update(source.encode('utf-8'))

        return hasher.hexdigest()

    def _register_cache(self, path):
        """
        Invoked on the root analysis by any descendant analyses that save's a
        cache file. This list of cache files is used once all analysis has
        completed to cleanup old cache files.
        """
        self._registered_cache_paths.append(path)

    def _cleanup_cache_files(self):
        """
        Deletes any cache files that exist in the cache directory which were
        not used when this analysis was last run.
        """
        for path in glob(os.path.join(self._cache_dir, '*.cache')):
            if path not in self._registered_cache_paths:
                os.remove(path)

    @memoize
    def _cache_path(self):
        """
        Get the full cache path for the current fingerprint.
        """
        return os.path.join(self._cache_dir, '%s.cache' % self._fingerprint())

    def _check_cache(self):
        """
        Check if there exists a cache file for the current fingerprint.
        """
        return os.path.exists(self._cache_path())

    def _save_cache(self, data):
        """
        Save the output data for this analysis from its cache.
        """
        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir)

        f = bz2.BZ2File(self._cache_path(), 'w')
        f.write(pickle.dumps(data))
        f.close()

    def _load_cache(self):
        """
        Load the output data for this analysis from its cache.
        """
        f = bz2.BZ2File(self._cache_path())
        data = pickle.loads(f.read())
        f.close()

        return data

    def then(self, next_func):
        """
        Create a new analysis which will run after this one has completed with
        access to the data it generated.

        :param func: A callable that implements the analysis. Must accept a
            `data` argument that is the state inherited from its ancestors
            analysis.
        """
        analysis = Analysis(next_func, cache_dir=self._cache_dir, _parent=self)

        self._next_analyses.append(analysis)

        return analysis

    def run(self, data={}, refresh=False):
        """
        Execute this analysis and its descendents. There are four possible
        execution scenarios:

        1. This analysis has never been run. Run it and cache the results.
        2. This analysis is the child of a parent analysis which was run, so it
           must be run because its inputs may have changed. Cache the result.
        3. This analysis has been run, its parents were loaded from cache and
           its fingerprints match. Load the cached result.
        4. This analysis has been run and its parents were loaded from cache,
           but its fingerprints do not match. Run it and cache updated results.

        On each run this analysis will clear any unused cache files from the
        cache directory. If you have multiple analyses running in the same
        location, specify separate cache directories for them using the
        ``cache_dir`` argument to the the :class:`Analysis` constructor.

        :param data: The input "state" from the parent analysis, if any.
        :param refresh: Flag indicating if this analysis must refresh because
            one of its ancestors did.
        """
        self._registered_fingerprints = []

        if refresh:
            print('Refreshing: %s' % self._name)

            local_data = deepcopy(data)

            self._func(local_data)
            self._save_cache(local_data)
        else:
            fingerprint = self._fingerprint()

            if self._check_cache():
                print('Loaded from cache: %s' % self._name)

                local_data = self._load_cache()
            else:
                print('Running: %s' % self._name)

                local_data = deepcopy(data)

                self._func(local_data)
                self._save_cache(local_data)

                refresh = True

        for analysis in self._next_analyses:
            analysis.run(local_data, refresh)

        self._root()._register_cache(self._cache_path())

        if self._root() is self:
            self._cleanup_cache_files()
