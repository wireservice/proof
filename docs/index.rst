===============
proof |release|
===============

About
=====

.. include:: ../README

Installation
============

Users
-----

If you only want to use proof, install it this way::

    pip install proof

Developers
----------

If you are a developer that also wants to hack on proof, install it this way::

    git clone git://github.com/onyxfish/proof.git
    cd proof
    mkvirtualenv proof
    pip install -r requirements.txt
    python setup.py develop
    tox

.. note::

    proof also supports running tests with coverage::

        nosetests --with-coverage --cover-package=proof

Supported platforms
-------------------

proof supports the following versions of Python:

* Python 2.6+
* Python 3.2+
* Latest `PyPy <http://pypy.org/>`_

It is tested on OSX, but due to it's minimal dependencies should work fine on both Linux and Windows.

Usage
=====

proof creates data processing pipelines by defining "analyses", each of which is a stage in the process. These analyses naturally flow from one to another. For instance, the first analysis of a process might load a CSV of data. From there you might select a subset of the rows in the table, then group the results and finally take the median of each group. More complex pipelines might alse diverge at some point, having several analyses that use the same input, but each produce different outputs.

proof contains a single class, :class:`Analysis`, which is used for creating processes like these. Each of the analyses is constructed by instantiating it with a function that does some work:

.. code-block:: python

    import proof

    def load_data(data):
        # Load the data
        pass

    data_loaded = proof.Analysis(load_data)

Analyses which depend on the result of this stage can then be created using the :meth:`Analysis.then` method.

.. code-block:: python

    def select_rows(data):
        # Select relevant rows from the table
        pass

    def calculate_average(data):
        # The average of a value in the rows is taken
        pass

    data_loaded.then(select_rows)
    data_loaded.then(calculate_average)

In the previous example, both ``select_rows`` and ``calculate_average`` depend on the result of ``load_data``. If instead we wanted our average to be based on only the selected rows, we would instead do:

.. code-block:: python

    rows_selected = data_loaded.then(select_rows)
    rows_selected.then(calculate_average)

Each analysis function must accept a ``data`` argument, which is a :class:`dict` of data to be persisted between analyses. Modifications made to ``data`` in the scope of one analysis will be propogated to all dependent analyses. For example, the three functions we saw before might be implemented like this:

.. code-block:: python

    import csv

    def load_data(data):
        # Load the data
        with open('example.csv') as f:
            reader = csv.DictReader(f, fieldnames=['name', 'salary'])
            reader.next()
            data['table'] = list(reader)

    def select_rows(data):
        # Select relevant rows from the table
        data['low_income'] = filter(lambda r: int(r['salary']) < 25000, data['table'])

    def calculate_average(data):
        # The average of a value in the rows is taken
        mean = sum([int(r['salary']) for r in data['low_income']]) / len(data['low_income'])
        print(mean)

We can see here how the ``data`` dictionary gets passed from function to function with it's state intact. You can also modify values that already exist in data and those changes will be propogated forward.

Finally, we run the analysis, starting at the beginning, by calling :meth:`.Analysis.run`:

.. code-block:: python

    data_loaded.run()

If we execute `the script we've created <https://github.com/onyxfish/proof/blob/master/example.py>`_, the output is:

::

    Running: load_data
    Refreshing: select_rows
    Refreshing: calculate_average
    13500

When :meth:`Analysis.run` is invoked, the analysis function runs, followed by each of dependent analyses created with :meth:`Analysis.then`. These in turn invoke their own dependent analyses, allowing a hierarchy to be created. Within each of those functions you can do whatever you want--print to the console, import other dependencies, save to disk--proof doesn't care *how* you analyze your data.

After each analysis the value of ``data`` is cached to disk along with a "fingerprint" describing the source code of the analysis function at the time it was invoked. If you run the same analysis twice without modifying the code, the cached version out of the ``data`` will be used for its dependents. This allows you to experiment with a dependent analysis without constantly recomputing the results of its parent. For example, if I rerun the previous script, I will see:

::

    Loaded from cache: load_data
    Loaded from cache: select_rows
    Loaded from cache: calculate_average

This indicates that the results of each analysis were loaded from disk. proof tries to be very smart about how much work it does. So, for instance, if you modify the middle analysis in this process, ``select_rows``, only it and other analyses that depend on it will be rerun. Try modifying the threshold for ``low_income`` down to ``20000`` and rerun the script. You should see:

::

    Loaded from cache: load_data
    Running: select_rows
    Refreshing: calculate_average
    10666

.. warning::

    One very important caveat exists to this automated dependency resolution. The fingerprint which is generated for each analysis function is **not recursive**, which is to say, it does not include the source of any functions which are invoked by that function. If you modify the source of a function invoked by the analysis function, you will need to ensure that the analysis is manually refreshed by passing ``refresh=True`` to :meth:`Analysis.run` or deleting the cache directory (``.proof`` by default).

API
===

There is only one class!

.. autoclass:: proof.analysis.Analysis
    :members:

Authors
=======

.. include:: ../AUTHORS

License
=======

.. include:: ../COPYING

Changelog
=========

.. include:: ../CHANGELOG

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
