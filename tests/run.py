#!/usr/bin/env python3
"""Roda todos os testes do Omni36OS. Saída 0 = tudo certo (o gancho de commit depende disso)."""
import os
import sys
import unittest

here = os.path.dirname(os.path.abspath(__file__))
suite = unittest.defaultTestLoader.discover(here, pattern="test_*.py")
ok = unittest.TextTestRunner(verbosity=1 if "-q" in sys.argv else 2).run(suite).wasSuccessful()
sys.exit(0 if ok else 1)
