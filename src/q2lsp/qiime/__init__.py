"""QIIME metadata and discovery.

Import q2cli_gateway explicitly for discovery. Importing catalog facts or pure
option helpers must not eagerly import q2cli and its environment dependencies.
"""
