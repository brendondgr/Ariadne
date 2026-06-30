"""Ariadne web service layer.

A thin FastAPI application that exposes the existing ``utils/`` capabilities
(live-source health, the federated query pipeline, LLM/connection configuration,
and infrastructure control) to the Next.js workbench under ``web/``. The service
wraps the same functions ``main.py`` calls — it does not re-implement any logic.
"""
