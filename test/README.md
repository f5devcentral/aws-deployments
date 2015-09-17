# README.md

These tests should be run before checking code into the master branch on the public github account. You are responsible for this, as there is no CI framework for this code. 

Proper testing will ensure the scripts provided in are kept in working order.

Run tests (from the top-level directory) via:
(venv)vagrant@f5demo:/aws-deployments$ py.test ./test

to run a specific test:
py.test ./test/test_images.py