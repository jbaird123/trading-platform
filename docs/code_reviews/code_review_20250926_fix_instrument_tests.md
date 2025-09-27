# Code Review: Changes Required

**Date:** 2025-09-26
**Subject:** Fix Remaining Instrument Tests

The implementation is functionally correct and well-tested, but it is non-compliant with project standards. The following changes are required before this can be approved. Address every item on this list precisely.

---

### **Required Changes**

*   **1. Fix Line Length Violations:** All code must be wrapped to a maximum of 88 characters per line. The following files contain violations and must be corrected:
    *   `tests/core/test_run.py`
    *   `tests/core/test_sweeps.py`
    *   `tests/core/test_walk_forward_optimize_and_test.py`
