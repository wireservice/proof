0.4.0 - February 23, 2024
-------------------------

* Use Python's logging module instead of ``print()``.
* Add support for recent Python versions.
* Drop support for end-of-life Python versions.

0.3.0 - September 24, 2015
--------------------------

* Fix errors when caching unicode analysis function names.
* Fix errors when caching unicode source. (#10)
* Add six dependency.
* Add decorator and logic for analysis functions that are never cached. (#5)

0.2.0 - September 2, 2015
-------------------------

* Don't load analysis cache unless needed. (#1)

0.1.0 - August 31, 2015
-----------------------

* Initial code migration from agate.
