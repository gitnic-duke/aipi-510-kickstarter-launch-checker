"""Shared input/output schema for the Kickstarter Launch Checker.

Shared contract (task T3): the API, training pipeline and front-end all import
this module so feature names can't drift apart. Only fields a creator knows on
launch day belong here — never post-launch fields like pledged or backers.
"""
