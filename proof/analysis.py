"""
This module contains the :class:`Analysis` class, which is used for creating
optimized, repeatable data processing workflows. An analysis can be created
from a function or any other callable object. Dependent analyses can then be
created using the :meth:`Analysis.then` method. Each function must accept a
``data`` argument, which is a :class:`dict` of data to be persisted between
analyses. Modifications made to ``data`` in the scope of one analysis will be
propagated to all dependent analyses.
"""

import bz2
import hashlib
import inspect
import logging
import os
import pickle
from copy import deepcopy
from glob import glob

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
logger.addHandler(ch)


class Cache:
    """
    Utility class for managing cached data.
    """

    def __init__(self, cache_path):
        self._cache_path = cache_path
        self._data = None

    def check(self):
        """
        Cache if a cache file exists.
        """
        return os.path.exists(self._cache_path)

    def get(self):
        """
        Get cached data from memory or disk.
        """
        if self._data is None:
            f = bz2.BZ2File(self._cache_path)
            self._data = pickle.loads(f.read())
            f.close()

        return deepcopy(self._data)

    def set(self, data):
        """
        Set cached data and write to disk.
        """
        self._data = data

        f = bz2.BZ2File(self._cache_path, 'w')
        f.write(pickle.dumps(self._data))
        f.close()


def never_cache(func):
    """
    Decorator to flag that a given analysis function should never be cached.
    """
    func.never_cache = True

    return func


class Analysis:
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
    :param _trace: The ancestors this analysis, if any. For internal use
        only.
    """

    def __init__(self, func, cache_dir='.proof', _trace=[]):
        self._name = func.__name__
        self._func = func
        self._cache_dir = cache_dir
        self._trace = _trace + [self]
        self._child_analyses = []

        self._cache_path = os.path.join(self._cache_dir, '%s.cache' % self._fingerprint())
        self._cache = Cache(self._cache_path)

        self._registered_cache_paths = []
        self._trace[0]._registered_cache_paths.append(self._cache_path)

    def _fingerprint(self):
        """
        Generate a fingerprint for this analysis function.
        """
        hasher = hashlib.md5()

        history = '\n'.join([analysis._name for analysis in self._trace])

        # In Python 3 function names can be non-ascii identifiers
        history = history.encode('utf-8')

        hasher.update(history)

        source = inspect.getsource(self._func)

        # In Python 3 inspect.getsource returns unicode data
        source = source.encode('utf-8')

        hasher.update(source)

        return hasher.hexdigest()

    def _cleanup_cache_files(self):
        """
        Deletes any cache files that exist in the cache directory which were
        not used when this analysis was last run.
        """
        for path in glob(os.path.join(self._cache_dir, '*.cache')):
            if path not in self._registered_cache_paths:
                os.remove(path)

    def then(self, child_func):
        """
        Create a new analysis which will run after this one has completed with
        access to the data it generated.

        :param func: A callable that implements the analysis. Must accept a
            `data` argument that is the state inherited from its ancestors
            analysis.
        """
        analysis = Analysis(
            child_func,
            cache_dir=self._cache_dir,
            _trace=self._trace
        )

        self._child_analyses.append(analysis)

        return analysis

    def run(self, refresh=False, _parent_cache=None):
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

        :param refresh: Flag indicating if this analysis must refresh because
            one of its ancestors did.
        :parent _parent_cache: Data cache for the parent analysis. For internal
            usage only.
        """
        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir)

        do_not_cache = getattr(self._func, 'never_cache', False)

        if refresh is True:
            logger.info('Refreshing: %s' % self._name)
        elif do_not_cache:
            refresh = True

            logger.info('Never cached: %s' % self._name)
        elif not self._cache.check():
            refresh = True

            logger.info('Stale cache: %s' % self._name)

        if refresh:
            if _parent_cache:
                local_data = _parent_cache.get()
            else:
                local_data = {}

            self._func(local_data)

            if not do_not_cache:
                self._cache.set(local_data)
        else:
            logger.info('Deferring to cache: %s' % self._name)

        for analysis in self._child_analyses:
            analysis.run(refresh=refresh, _parent_cache=self._cache)

        if self._trace[0] is self:
            self._cleanup_cache_files()
